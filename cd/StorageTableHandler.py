from azure.data.tables import TableServiceClient, TableClient
from azure.core.credentials import AzureNamedKeyCredential


class StorageTableHandlerException(Exception):
    def __init__(self, error_msg):
        super().__init__(self)
        self._error_msg = error_msg

    def __str__(self):
        return self._error_msg


class StorageTableHandlerClass:
    def __init__(self, endpoint, account_name, access_key):
        self._endpoint = endpoint
        self._account_name = account_name
        self._access_key = access_key

    def init_client(self):
        account_credential = AzureNamedKeyCredential(self._account_name, self._access_key)
        return TableServiceClient(endpoint=self._endpoint, credential=account_credential)

    def query_tables(self, storage_table_name, name_filter, select_rows=None):
        try:
            with self.init_client() as table_service_client:
                table_client = table_service_client.get_table_client(table_name=storage_table_name)
                with table_client:
                    queried_entities = table_client.query_entities(query_filter=name_filter,
                                                                   select=select_rows)
                    rst_entities = list(queried_entities).copy()
        except Exception as err:
            err_msg = f"StorageTableHandlerClass-query_data:{err.__class__} occurred."
            raise StorageTableHandlerException(err_msg)
        if len(rst_entities) == 0:
            print(f"query result is none - query_filter:{name_filter} - select:{select_rows} ")
        return rst_entities

    def insert_data(self, storage_table_name, params):
        try:
            with self.init_client() as table_service_client:
                table_client = table_service_client.get_table_client(table_name=storage_table_name)
                with table_client:
                    insert_entity = table_client.upsert_entity(entity=params)
                    print(f"insert entity:{repr(insert_entity)}")
        except Exception as err:
            err_msg = f"StorageTableHandlerClass-insert_data:{err.__class__} occurred."
            raise StorageTableHandlerException(err_msg)


def run_test():
    pass


if __name__ == '__main__':
    run_test()
