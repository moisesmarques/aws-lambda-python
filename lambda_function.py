import json
import boto3
import logging
import pyodbc

ssm_client = boto3.client('ssm')

def lambda_handler(event, context):

    try:
        
        clientconfig_control = get_clientconfig_control()
        clientconfig_control_original = set(clientconfig_control)
        clientconfig_control_current = set()
        connection_string = get_connection_string()
        connection = pyodbc.connect(connection_string)
        
        with connection:
            cursor = connection.cursor()
            rows = get_all_client_config(cursor)
            
            for row in rows:
                add_update_parameter(clientconfig_control_current, row)
                
            delete_unused_parameters(clientconfig_control_original, clientconfig_control_current)
            update_clientconfig_control(clientconfig_control_current)
                
        return {
            'statusCode': 200,
            'body': None
            }

    except Exception as e:
        logging.error(e)
        return {
            'statusCode': 500,
            'body': None
            }

		
def get_parameter(parameter):
    
    response = ssm_client.get_parameter(
        Name=parameter,
        WithDecryption=True
    )
    json_response = json.loads(response["Parameter"]["Value"])

    return json_response

def get_connection_string():
    connection_params = get_parameter("DB_CONFIG")
        
    return 'DRIVER={ODBC Driver 17 for SQL Server};' + """SERVER={0};DATABASE={1};UID={2};PWD={3}""".format(
        connection_params['host_name'],
        connection_params['database_name'],
        connection_params['user_name'],
        connection_params['user_password'] )
        
def get_clientconfig_control():
    try:
        return get_parameter("db_config")
    except:
        return []
        
def get_all_client_config(cursor):
    sql_query = """
                    SELECT * FROM
            """

    return cursor.execute(sql_query).fetchall()
        
def add_update_parameter(clientconfig_control_current, row):
    
    shortName = row.ShortName.lower()
    
    clientconfig_control_current.add(shortName)
    
    firebird = firebird_configuration(
                        row.Usuario,
                        row.Senha,
                        row.IP,
                        "",
                        row.Path)
                        
    sql = sql_configuration(
            row.AptitudeUsuario,
            row.AptitudeSenha,
            row.AptitudeIP)
            
    ssm_client.put_parameter(
        Name="/applications/repcenter/db/{0}".format(shortName),
        Value=client_configuration(
            row.LongName,
            firebird,
            sql).toJSON(),
        Type='SecureString',
        Overwrite=True
    )
        
def delete_unused_parameters(clientconfig_control_original, clientconfig_control_current):
    
    shortNames = clientconfig_control_original.difference(clientconfig_control_current)
    
    for shortName in list(shortNames):
        try:
            ssm_client.delete_parameter(
                Name="/db_config/{0}".format(shortName)
            )
        except:
            print("Deleting unused parameter {0}. Parameter not found.".format(shortName))
        
def update_clientconfig_control(clientconfig_control_current):
    
    ssm_client.put_parameter(
        Name="db_config_control",
        Description="Control of all config parameters existents.",
        Value= json.dumps(list(clientconfig_control_current)),
        Type='SecureString',
        Overwrite=True,
    )
        
class firebird_configuration(object):
    
    def __init__(self, username: str, password: str, host: str, port: str, path: str):
        self.user = username
        self.password = password
        self.host = host
        self.port = port
        self.path = path
    
class sql_configuration(object):
    
    def __init__(self, username: str, password: str, host: str):
        self.user = username
        self.password = password
        self.host = host
    
class client_configuration(object):

    def __init__(self, long_name: str, firebird: firebird_configuration, sql: sql_configuration):
        
        self.long_name = long_name
        self.firebird = firebird
        self.sql = sql

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, 
            sort_keys=False, indent=4)