import getopt
import sys

import AdminUtilities

import env


def set_server_sdk(nodeName, serverName):
    AdminTask.setServerSDK(['-nodeName', nodeName, '-serverName', serverName, '-sdkName', '1.7_64'])

def create_required_jvm_cust_props(nodeName, serverName):
    for (name, val) in env.JVM_CUSTOM_PROPERTIES.items():
        AdminTask.setJVMSystemProperties(["-nodeName", nodeName, "-serverName", serverName, "-propertyName", name, "-propertyValue", val])
        print "\nSetting JVM System Property '%s' to '%s'." % (name, val)
        

def create_JDBC_provider(nodeName, serverName, jdbc_provider):
    # check if object already exist
    jdbc = AdminConfig.getid("/Node:%s/Server:%s/JDBCProvider:%s/" % (nodeName, serverName, jdbc_provider))
    if (len(jdbc) == 0):
        result = AdminTask.createJDBCProvider(["-scope", "Node=%s,Server=%s" %(nodeName, serverName), "-databaseType", "Oracle", "-providerType", "Oracle JDBC Driver", "-implementationType", "Connection pool data source", "-name", jdbc_provider , "-description", jdbc_provider, "-classpath", ["${ORACLE_JDBC_DRIVER_PATH}/ojdbc6.jar"], "-nativePath", "" ])
        return result
    else:
        print "JDBCProvider %s already exists." % jdbc_provider
        return jdbc

def create_datasources_for_environment(env_name, serverName=None, nodeName=None, jdbc_provider=None):
    if nodeName is None:
        nodeName = AdminControl.getNode()
    if serverName is None:
        serverObjName = AdminControl.completeObjectName('node=%s,type=Server,*' % nodeName)
        serverName = AdminControl.getAttribute(serverObjName, 'name')
    if jdbc_provider is None:
        jdbc_provider = "Oracle JDBC Driver"
        
    if env_name not in env.CONFIG_INFO.keys():
        print "'%s' is not a known environment name. Please use one of %s" % (env_name, env.CONFIG_INFO.keys())
        return
        
    for (ds_type,ds_info) in env.CONFIG_INFO[env_name]["datasources"].items():
        create_datasource(serverName, nodeName, jdbc_provider, ds_info)


def create_datasource(serverName, nodeName, jdbc_provider, ds_info):
    if ds_info["jndi"] and ds_info["url"] and ds_info["name"] and ds_info["username"] and ds_info["password"]:
        ds_id = AdminConfig.getid('/Node:%s/Server:%s/JDBCProvider:%s/DataSource:%s/' % (nodeName, serverName, jdbc_provider, ds_info["name"]))
        if ds_id == "":
            gen_auth_entry_name = ""
            try:
                gen_auth_entry_name = "%s/%s" % (nodeName, ds_info["username"])
                try: 
                    entry_id = AdminTask.getAuthDataEntry(['-alias', gen_auth_entry_name])
                except:
                    entry_id = AdminTask.createAuthDataEntry(['-alias', ds_info["username"], '-user', ds_info["username"], '-password', ds_info["password"]])
                    AdminConfig.save()
                jdbc_provider_id = create_JDBC_provider(nodeName, serverName, jdbc_provider)
                ds_attribs = [['name', ds_info["name"]], 
                              ["jndiName", ds_info["jndi"]], 
                              ["authDataAlias", gen_auth_entry_name], 
                              ["datasourceHelperClassname", "com.ibm.websphere.rsadapter.Oracle11gDataStoreHelper"],
                              ["mapping", [['authDataAlias' , gen_auth_entry_name] , ["mappingConfigAlias", "DefaultPrincipalMapping"]]]]

                new_ds_id = AdminConfig.create('DataSource', jdbc_provider_id, ds_attribs)
                propSet = AdminConfig.create('J2EEResourcePropertySet', new_ds_id, [])
                property = AdminConfig.create('J2EEResourceProperty', propSet, [["name", "URL"], ["value", ds_info["url"]]])

                print "\nCreated a datasource: jndi: '%s'  url: '%s'  name: '%s'  username: '%s'  password: '%s'" % (ds_info["jndi"], ds_info["url"], ds_info["name"], ds_info["username"], ds_info["password"])
                AdminConfig.save()
            except: 
                typ, val, tb = sys.exc_info()
                print "\nException %s trying to create DataSource '%s' with message %s\n    alias name: %s\n    jndi: %s\n    url: %s\n    username: %s" % (typ, ds_info["name"], val, gen_auth_entry_name, ds_info["jndi"], ds_info["url"], ds_info["username"])

        else:
            print "\nThere already exists a datasource with the name '%s'" % ds_info["name"]

    else:
        print "\nThere is not enough information to create a datasource: jndi: '%s'  url: '%s'  name: '%s'  username: '%s'  password: '%s'" % (ds_info["jndi"], ds_info["url"], ds_info["name"], ds_info["username"], ds_info["password"])

        
def get_environment_name_currently_configured():
        
    datasources = AdminConfig.list('DataSource').splitlines()
    # Find the datasource currently configured to access the ECommerce Database, with the jndi of jdbc/cipo/ec/defaultDS
    ecom_ds = ds_name = None
    for datasource in datasources:
        jndi = AdminConfig.showAttribute(datasource,'jndiName')
        if jndi == "jdbc/cipo/ec/defaultDS":
            ds_name = AdminConfig.showAttribute(datasource,'name')
            ecom_ds = datasource
            break
    if not ecom_ds:
        print "Cannot find name of environment currently configured. Could not find current ECommerce datasource."
        return None
    for env_name in env.CONFIG_INFO.keys():
        if env.CONFIG_INFO[env_name]["datasources"]["ecommerce"]["name"] == ds_name:
            return env_name
    print "Cannot find name of environment currently configured. Could not find name of current ECommerce datasource, %s, in environment configurations." % ds_name
    return None        

def switch_environment(new_env, serverName=None, nodeName=None, jdbc_provider=None):
    if nodeName is None:
        nodeName = AdminControl.getNode()
    if serverName is None:
        serverObjName = AdminControl.completeObjectName('node=%s,type=Server,*' % nodeName)
        serverName = AdminControl.getAttribute(serverObjName, 'name')
    if jdbc_provider is None:
        jdbc_provider = "Oracle JDBC Driver"

    old_env_property = AdminTask.showJVMSystemProperties(["-nodeName", nodeName, "-serverName", serverName, "-propertyName", "ENVIRONMENT"])

    # Need to confirm that the new environment resources have been created 
    ds_name = env.CONFIG_INFO[new_env]["datasources"]["ecommerce"]["name"]
    datasource_id = AdminConfig.getid("/Node:%s/Server:%s/JDBCProvider:%s/DataSource:%s/" % (nodeName, serverName, jdbc_provider, ds_name))
    if not datasource_id:
        print "\nNeed to create the resources for the %s environment first" % new_env
        create_datasources_for_environment(new_env)
    else:
        print "\nUsing existing resources for the %s environment first" % new_env
        
    old_env_name = get_environment_name_currently_configured()
        
    if old_env_property == new_env:

        datasources = AdminConfig.list('DataSource').splitlines()
        print "\nChanging current datasources with the runtime jndi values to those for the %s environment." % old_env_name
        # Change the jndi values for the current runtime datasources back to their environment specific values
        for datasource in datasources:
            ds_name = AdminConfig.showAttribute(datasource,'name')
            jndi = AdminConfig.showAttribute(datasource,'jndiName')
            if jndi in env.RUNTIME_DATASOURCE_JNDIS.keys():
                datasource_type = env.RUNTIME_DATASOURCE_JNDIS[jndi]
                env_jndi = env.CONFIG_INFO[old_env_name]["datasources"][datasource_type]["jndi"]
                AdminConfig.modify(datasource, [["jndiName", env_jndi]])
                print "Changed jndi of datasource '%s' from '%s' to '%s'." % (ds_name, jndi, env_jndi)

        print "\nChanging %s environment datasources jndi values to those of the the runtime  environment." % new_env
        
        # Change the jndi values for the new environment datasources to the runtime specific values
        for jndi in env.RUNTIME_DATASOURCE_JNDIS.keys():
            datasource_type = env.RUNTIME_DATASOURCE_JNDIS[jndi]
            ds_name = env.CONFIG_INFO[new_env]["datasources"][datasource_type]["name"]
            datasource_id = AdminConfig.getid("/Node:%s/Server:%s/JDBCProvider:%s/DataSource:%s/" % (nodeName, serverName, jdbc_provider, ds_name))
            if datasource_id != '':
                old_jndi = AdminConfig.showAttribute(datasource_id,'jndiName')
                AdminConfig.modify(datasource_id, [["jndiName", jndi]])
                print "Changed jndi of datasource '%s' from '%s' to '%s'." % (ds_name, old_jndi, jndi)
            else:
                print "Does not appear to be a datasource with the name %s" % ds_name 

        AdminTask.setJVMSystemProperties(["-nodeName", nodeName, "-serverName", serverName, "-propertyName", "ENVIRONMENT", "-propertyValue", env.CONFIG_INFO[new_env]["environment"]])
        print "\nChanged JVM System Property 'ENVIRONMENT' from '%s' to '%s'." % (old_env_property, env.CONFIG_INFO[new_env]["environment"])
        AdminConfig.save()
    else:
        print "\nIt appears that the environment is already set to %s" % new_env

    display_current_environment(serverName, nodeName)


def test_datasources(env_name=None):
    if not env_name:
        env_name = get_environment_name_currently_configured()   
    for (ds_type, ds_info) in env.CONFIG_INFO[env_name]["datasources"].items():
        ds_id = AdminConfig.getid('/DataSource:%s/' % ds_info["name"])
        if ds_id != "":
            try:
                print "\nTesting connection of datasource %s:" % ds_info["name"]
                print AdminControl.testConnection(ds_id)
            except:
                typ, val, tb = sys.exc_info()
                print "Exception %s trying to test connection of DataSource '%s' with message %s" % (typ, ds_info["name"], val)
        else:
            print "Cannot find DataSource with the name '%s' to test!" % ds_info["name"]


def display_current_environment(serverName=None, nodeName=None):
    if nodeName is None:
        nodeName = AdminControl.getNode()
    if serverName is None:
        serverObjName = AdminControl.completeObjectName('node=%s,type=Server,*' % nodeName)
        serverName = AdminControl.getAttribute(serverObjName, 'name')

    old_env_name = get_environment_name_currently_configured()
    env_property = AdminTask.showJVMSystemProperties(["-nodeName", nodeName, "-serverName", serverName, "-propertyName", "ENVIRONMENT"])

    print "\n\nCurrent environment setting for %s environment:\n\nJVM System Property:\n\nENVIRONMENT: '%s'" % (old_env_name, env_property)

    datasources = AdminConfig.list('DataSource').splitlines()

    for datasource in datasources:
        ds_name = AdminConfig.showAttribute(datasource,'name')       
        jndi = AdminConfig.showAttribute(datasource,'jndiName')
        if jndi in env.RUNTIME_DATASOURCE_JNDIS.keys():
            print "\n\nDatasource: " + ds_name
            print "JNDI: " + jndi
            print "authDataAlias: " + AdminConfig.showAttribute(datasource,'authDataAlias')

            propertySet = AdminConfig.showAttribute(datasource,'propertySet')
            propertyList = AdminConfig.list('J2EEResourceProperty', propertySet).splitlines()        
            for property in propertyList:
                    propName = AdminConfig.showAttribute(property, 'name')
                    if propName == "URL":
                        propValue = AdminConfig.showAttribute(property, 'value')
                        print propName + " : " + propValue


def test():
    # import switch_environment
    # import env
    nodeName = AdminControl.getNode()
    serverObjName = AdminControl.completeObjectName('node=%s,type=Server,*' % nodeName)
    serverName = AdminControl.getAttribute(serverObjName, 'name')
    ds_info = env.CONFIG_INFO["UAT"]["datasources"][""]
    
def create_datasources(env_name):
    nodeName = AdminControl.getNode()
    serverObjName = AdminControl.completeObjectName('node=%s,type=Server,*' % nodeName)
    serverName = AdminControl.getAttribute(serverObjName, 'name')
    jdbc_provider = "Oracle JDBC Driver"

    create_datasources_for_environment(env_name, serverName, nodeName, jdbc_provider)
    
    display_current_environment(serverName, nodeName)

    
def usage():
    print "\nwsadmin.bat -f switch_environment.py [<options>]"
    print "\nWith <options> being one of the following:"
    print "\t--help              - This usage help information"
    print "\t-v                  - Set the display to Verbose to display additional information"
    print "\t-d or --display     - Display the current settings for the WAS server"
    print "\t-l or --list        - Display the list of available environment names to switch to"
    print "\t-e <environment name> or --environment <environment name>"
    print "\t                    - Switch the WAS configuration to the setting for the specified environment name. "
    print "\t                      The environment name must be one:", env.CONFIG_INFO.keys()
    
if __name__ == "__main__":\

    try:
        opts, args = getopt.getopt(sys.argv, "de:hltv", ["display", "environment=", "list", "help"])
    except getopt.GetoptError:
        # print help information and exit:
        print sys.exc_info()   # will print something like "option -a not recognized"
        usage()
        sys.exit(2)
    env_name = None
    verbose = None
    for o, a in opts:
        if o == "-v":
            verbose = True
        elif o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-d", "--display"):
            display_current_environment()
        elif o == "-t":
            test_datasources()
        elif o in ("-l", "--list"):
            print "The available environments are:"
            for env_key in env.CONFIG_INFO.keys():
                print "\t%s" % env_key
        elif o in ("-e", "--environment"):
            print "Switching the current environment to %s" % env_name
            env_name = a
            switch_environment(env_name)
        else:
            print "Unknown option '%s' with value '%s'" % (o, a)
