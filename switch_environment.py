import sys

import AdminUtilities

import env


def create_JDBC_provider(nodeName, serverName, JDBCName):
    # check if object already exist
    jdbc = AdminConfig.getid("/Node:%s/Server:%s/JDBCProvider:%s/") % (nodeName, serverName, JDBCName)
    if (len(jdbc) == 0):
        result = AdminTask.createJDBCProvider(["-scope", "Node=%s,Server=%s" %(nodeName, serverName), "-databaseType", "Oracle", "-providerType", "Oracle JDBC Driver", "-implementationType", "Connection pool data source", "-name", JDBCName , "-description", JDBCName, "-classpath", ["${ORACLE_JDBC_DRIVER_PATH}/ojdbc6.jar"], "-nativePath", "" ])
        return result
    else:
        print "JDBCProvider %s already exists." % JDBCName
        return jdbc

def create_datasources_for_environment(serverName, nodeName, jdbc_provider, env_name):

    if env_name not in env.CONFIG_INFO.keys():
        print "'%s' is not a known environment name. Please use one of %s" % (env_name, env.CONFIG_INFO.keys())
        return
        
    for (ds_type,ds_info) in env.CONFIG_INFO[env_name]["datasources"].items():
        create_datasource(serverName, nodeName, jdbc_provider, ds_info)


def create_datasource(serverName, nodeName, jdbc_provider, ds_info):
    if ds_info["jndi"] and ds_info["url"] and ds_info["name"] and ds_info["username"] and ds_info["password"]:
        ds_id = AdminConfig.getid('/Node:%s/Server:%s/JDBCProvider:%s/DataSource:%s/' % (nodeName, serverName, jdbc_provider, ds_info["name"]))
        if ds_id == '':
            gen_auth_entry_name = "%s/%s" % (nodeName, ds_info["username"])
            if AdminTask.getAuthDataEntry(['-alias', gen_auth_entry_name]) == "":
                entry_id = AdminTask.createAuthDataEntry(['-alias', ds_info["username"], '-user', ds_info["username"], '-password', ds_info["password"]])
            jdbc_provider_id = create_JDBC_provider(nodeName, serverName, jdbc_provider)
            ds_attribs = [['name', ds_info["name"]], ['url', ds_info["url"]], ["jndiName", ds_info["jndi"]], ["authDataAlias", gen_auth_entry_name], ["datasourceHelperClassname", "com.ibm.websphere.rsadapter.Oracle11gDataStoreHelper"]]
            new_ds_id = AdminConfig.create('DataSource', jdbc_provider_id, ds_attribs)
            
            # new_ds_id = AdminTask.createDatasource(jdbc_provider_id, ["-name", ds_info["name"], "-jndiName", ds_info["jndi"], "-dataStoreHelperClassName", "com.ibm.websphere.rsadapter.Oracle11gDataStoreHelper", "-containerManagedPersistence", "true", "-componentManagedAuthenticationAlias", entry_id, "-configureResourceProperties", [["URL", "java.lang.String", ds_info["url"]]]])
            # AdminConfig.create('MappingModule', new_ds_id, [["authDataAlias", entry_id] [mappingConfigAlias ""]]')
            # AdminConfig.modify('(cells/W0537081Node01Cell/nodes/W0537081Node01/servers/server1|resources.xml#CMPConnectorFactory_1564778397577)', [["name", ds_info["name"] + "_CF"], ["authDataAlias", entry_id], ["xaRecoveryAuthAlias", ""]])
            # AdminConfig.create('MappingModule', '(cells/W0537081Node01Cell/nodes/W0537081Node01/servers/server1|resources.xml#CMPConnectorFactory_1564778397577)', '[[authDataAlias W0537081Node01/CIPO_ECOMM_PRJT_UAT_RW_USER] [mappingConfigAlias ""]]')
            print "Created a datasource: jndi: '%s'  url: '%s'  name: '%s'  username: '%s'  password: '%s'" % (ds_info["jndi"], ds_info["url"], ds_info["name"], ds_info["username"], ds_info["password"])
        else:
            print "There already exists a datasource with the name '%s'" % ds_info["name"]

        # return True            
    else:
        print "There is not enough information to create a datasource: jndi: '%s'  url: '%s'  name: '%s'  username: '%s'  password: '%s'" % (ds_info["jndi"], ds_info["url"], ds_info["name"], ds_info["username"], ds_info["password"])
    # return False


def switch_environment(serverName, nodeName, jdbc_provider, new_env):

    old_env_property = AdminTask.showJVMSystemProperties(["-nodeName", nodeName, "-serverName", serverName, "-propertyName", "ENVIRONMENT"])

    old_env_name = env.ENVIRONMENT_NAME_DICT[old_env_property]
    if old_env_property != env.CONFIG_INFO[new_env]["environment"]:

        datasources = AdminConfig.list('DataSource').splitlines()
        print "\nChanging current datasources with the runtime jndi values to those for the %s environment." % old_env_name
        # Change the jndi values for the current runtime datasources back to their environment specific values
        for datasource in datasources:
            dsName = AdminConfig.showAttribute(datasource,'name')
            jndi = AdminConfig.showAttribute(datasource,'jndiName')
            if jndi in env.RUNTIME_DATASOURCE_JNDIS.keys():
                datasource_type = env.RUNTIME_DATASOURCE_JNDIS[jndi]
                env_jndi = env.CONFIG_INFO[old_env_name]["datasources"][datasource_type]["jndi"]
                AdminConfig.modify(datasource, [["jndiName", env_jndi]])
                print "Changed jndi of datasource '%s' from '%s' to '%s'." % (dsName, jndi, env_jndi)

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


def test_datasources(env_name):
    for (ds_type, ds_info) in env.CONFIG_INFO[env_name]["datasources"].items():
        ds_id = AdminConfig.getid('/DataSource:%s/' % ds_info["name"])
        if ds_id != "":
            try:
                AdminControl.testConnection(ds_id)
            except:
                typ, val, tb = sys.exc_info()
                print "Exception %s trying to test connection of DataSource '%s' with message %s" % (typ, ds_info["name"], val)
        else:
            print "Cannot find DataSource with the name '%s' to test!" % ds_info["name"]


def display_current_environment(serverName, nodeName):

    env_property = AdminTask.showJVMSystemProperties(["-nodeName", nodeName, "-serverName", serverName, "-propertyName", "ENVIRONMENT"])

    print "\n\nCurrent environment setting:\n\nJVM System Property:\n\nENVIRONMENT: '%s'" % env_property

    datasources = AdminConfig.list('DataSource').splitlines()

    for datasource in datasources:
        dsName = AdminConfig.showAttribute(datasource,'name')       
        jndi = AdminConfig.showAttribute(datasource,'jndiName')
        if jndi in env.RUNTIME_DATASOURCE_JNDIS.keys():
            print "\n\nDatasource: " + dsName
            print "JNDI: " + jndi
            print "authDataAlias: " + AdminConfig.showAttribute(datasource,'authDataAlias')

            propertySet = AdminConfig.showAttribute(datasource,'propertySet')
            propertyList = AdminConfig.list('J2EEResourceProperty', propertySet).splitlines()        
            for property in propertyList:
                    propName = AdminConfig.showAttribute(property, 'name')
                    if propName == "URL":
                        propValue = AdminConfig.showAttribute(property, 'value')
                        print propName + " : " + propValue


if __name__ == "__main__": 
    serverName = "server1"
    nodeName = "W0537081Node01"
    jdbc_provider = "Oracle JDBC Driver"
    env_name = "uat"
    switch_environment.create_datasources_for_environment(serverName, nodeName, jdbc_provider, env_name)
    
    display_current_environment(serverName, nodeName)

    # switch_environment(serverName, nodeName, jdbc_provider, new_env)
