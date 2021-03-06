import pycassa
import json
from dnstypeconstants import *

def install_schema(drop_first=False, rf=3):
    keyspace_name = "dns"
    sm = pycassa.system_manager.SystemManager("127.0.0.1:9160")

    # Drop the keyspace first, if requested.
    if drop_first:
        props = None
        try:
            props = sm.get_keyspace_properties(keyspace_name)
        except pycassa.cassandra.ttypes.NotFoundException:
            pass
        if props is not None:
            sm.drop_keyspace(keyspace_name)

    sm.create_keyspace(keyspace_name, replication_factor=rf)
    sm.create_column_family(keyspace_name, "names", super=True,
                            key_validation_class=pycassa.system_manager.UTF8_TYPE,
                            comparator_type=pycassa.system_manager.UTF8_TYPE,
                            default_validation_class=pycassa.system_manager.UTF8_TYPE)

class CassandraNames:
    def __init__(self):
        self.pool = pycassa.connect("dns")

    def lookup(self, fqdn, type=ANY):
        cf = pycassa.ColumnFamily(self.pool, "names")
        try:
            columns = {}
            if type == ANY:
                # Pull all types of records.
                columns = dict(cf.get(fqdn))
            else:
                # Pull only one type of record.
                columns = {str(type): dict(cf.get(fqdn, super_column=str(type)))}

            # Convert the JSON metadata into valid Python data.
            decoded_columns = {}
            for type, entries in columns.items():
                decoded_columns[int(type)] = {}
                for data, metadata in entries.items():
                    decoded_columns[int(type)][data] = json.loads(metadata)
            return decoded_columns
        except pycassa.cassandra.ttypes.NotFoundException:
            # If no records exist for the FQDN or type, fail gracefully.
            pass
        return {}

    def insert(self, fqdn, type, data, ttl=900, preference=None):
        cf = pycassa.ColumnFamily(self.pool, "names")
        metadata = {"ttl": int(ttl)}
        if preference is not None:
            metadata["preference"] = int(preference)
        cf.insert(fqdn, {str(type): {data: json.dumps(metadata)}})

    def remove(self, fqdn, type=ANY, data=None):
        cf = pycassa.ColumnFamily(self.pool, "names")
        if type == ANY:
            # Delete all records for the FQDN.
            cf.remove(fqdn)
        elif data is None:
            # Delete all records of a certain type from the FQDN.
            cf.remove(fqdn, super_column=str(type))
        else:
            # Delete all records for a certain type and data.
            cf.remove(fqdn, super_column=str(type), columns=[data])
