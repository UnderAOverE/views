
# mongo_schema_tool.py
import pymongo
import os
import json
import logging
import argparse
from typing import Dict, Any, List, Tuple, Union, Set

# Import the connection manager
from mongo_client_manager import MongoManager # Assuming this file exists as previously defined

# Configure logging specifically for this tool
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - [%(levelname)s] - %(message)s')
logger = logging.getLogger("MongoSchemaTool")

# Mapping for index orders
INDEX_ORDER_MAP = {
    "ASCENDING": pymongo.ASCENDING,
    "DESCENDING": pymongo.DESCENDING,
    "HASHED": pymongo.HASHED,
    "GEOSPHERE": pymongo.GEOSPHERE,
    "TEXT": pymongo.TEXT
}

# --- Deletion Functions ---

def delete_collections(client: pymongo.MongoClient, collections_to_delete: List[str]):
    """Deletes specified collections."""
    if not collections_to_delete:
        logger.error("Action 'delete-collections' requires the --collections argument.")
        return False # Indicate failure/missing args
    # endIf
    logger.warning("--- Starting Collection Deletion ---")
    success_count = 0
    fail_count = 0
    skipped_count = 0
    for full_coll_name in collections_to_delete:
        parts = full_coll_name.split('.', 1)
        if len(parts) != 2:
            logger.error(f"Invalid format for collection to delete: '{full_coll_name}'. Use 'database_name.collection_name'. Skipping.")
            skipped_count += 1
            continue
        # endIf
        db_name, coll_name = parts
        try:
            db = client[db_name]
            existing_collections = db.list_collection_names()
            if coll_name in existing_collections:
                logger.warning(f"Attempting to drop collection: '{db_name}.{coll_name}'...")
                db.drop_collection(coll_name)
                logger.info(f"Successfully dropped collection: '{db_name}.{coll_name}'.")
                success_count += 1
            else:
                logger.warning(f"Collection '{db_name}.{coll_name}' not found. Skipping deletion.")
                skipped_count += 1
            # endIfElse
        except Exception as e:
            logger.error(f"Failed to drop collection '{db_name}.{coll_name}': {e}", exc_info=True)
            fail_count += 1
        # endTryExcept
    # endFor
    logger.warning(f"--- Collection Deletion Finished (Deleted: {success_count}, Not Found: {skipped_count}, Failed: {fail_count}) ---")
    return fail_count == 0 # Return True if no failures occurred
# endDef

def delete_databases(client: pymongo.MongoClient, databases_to_delete: List[str]):
    """Deletes specified databases. This removes all collections within them."""
    if not databases_to_delete:
        logger.error("Action 'delete-databases' requires the --databases argument.")
        return False # Indicate failure/missing args
    # endIf
    logger.warning("--- Starting Database Deletion ---")
    success_count = 0
    fail_count = 0
    skipped_count = 0
    try:
        existing_dbs = set(client.list_database_names())
    except Exception as e:
        logger.error(f"Failed to list existing databases for deletion check: {e}. Aborting deletions.")
        return False
    # endTryExcept

    for db_name in databases_to_delete:
        if not db_name or db_name in ['admin', 'local', 'config']: # Protect system DBs
            logger.error(f"Invalid or protected database name for deletion: '{db_name}'. Skipping.")
            skipped_count += 1
            continue
        # endIf
        try:
            if db_name in existing_dbs:
                logger.warning(f"Attempting to drop database: '{db_name}' (and all its contents)...")
                client.drop_database(db_name)
                logger.info(f"Successfully dropped database: '{db_name}'.")
                success_count += 1
            else:
                logger.warning(f"Database '{db_name}' not found. Skipping deletion.")
                skipped_count += 1
            # endIfElse
        except Exception as e:
            logger.error(f"Failed to drop database '{db_name}': {e}", exc_info=True)
            fail_count += 1
        # endTryExcept
    # endFor
    logger.warning(f"--- Database Deletion Finished (Deleted: {success_count}, Not Found: {skipped_count}, Failed: {fail_count}) ---")
    return fail_count == 0 # Return True if no failures occurred
# endDef


# --- Schema Application Function ---

def apply_schema(client: pymongo.MongoClient, schema_config_path: str, environment: str):
    """
    Loads schema config and ensures defined databases, collections, and indexes exist.
    This version correctly handles compound indexes.
    """
    logger.info(f"Loading schema configuration from: {schema_config_path}")
    try:
        with open(schema_config_path, 'r') as f:
            schema_full_config = json.load(f)
        # endWith
    except FileNotFoundError:
        logger.error(f"Schema configuration file not found: {schema_config_path}")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {schema_config_path}: {e}")
        return False
    # endTryExcept

    if environment not in schema_full_config.get('environments', {}):
         logger.error(f"Environment '{environment}' not found in schema config file: {schema_config_path}")
         return False
    # endIf
    env_schema_config = schema_full_config['environments'][environment]
    logger.info(f"Selected schema for environment: '{environment}' - {env_schema_config.get('description', 'No description')}")

    defined_dbs = env_schema_config.get('databases', {})
    if not defined_dbs:
        logger.info("No databases defined in the schema configuration for this environment.")
        return True
    # endIf

    logger.info(f"--- Starting Schema Enforcement for environment: '{environment}' ---")
    overall_success = True

    for db_name, db_config in defined_dbs.items():
        db_success = True
        logger.info(f"Processing database definition: '{db_name}'")
        try:
            db = client[db_name]
            defined_collections = db_config.get('collections', {})

            if not defined_collections:
                logger.warning(f"Database '{db_name}' is defined but contains no collections.")
                continue
            # endIf

            try:
                 existing_collections = set(db.list_collection_names())
                 logger.debug(f"Existing collections in '{db_name}': {existing_collections}")
            except Exception as e:
                 logger.error(f"Could not list collections for database '{db_name}': {e}. Skipping schema enforcement for this DB.")
                 db_success = False; overall_success = False; continue
            # endTryExcept

            for coll_name, coll_config in defined_collections.items():
                coll_success = True
                logger.info(f"-- Processing collection: '{db_name}.{coll_name}'")
                collection_exists = coll_name in existing_collections
                
                if 'capped' in coll_config:
                    if not collection_exists:
                        try:
                            cap_opts = coll_config['capped']
                            if 'size' not in cap_opts:
                                logger.error(f"   Capped collection '{coll_name}' missing required 'size' option. Skipping creation."); coll_success=False; continue
                            # endIf
                            logger.info(f"   Collection doesn't exist. Creating capped collection '{coll_name}'...")
                            db.create_collection(coll_name, capped=True, **cap_opts)
                            logger.info(f"   Successfully created capped collection '{coll_name}'.")
                            collection_exists = True
                        except pymongo.errors.CollectionInvalid:
                             logger.warning(f"   Capped collection '{coll_name}' already exists (race condition). Proceeding.")
                             collection_exists = True
                        except Exception as e:
                             logger.error(f"   Failed to create capped collection '{coll_name}': {e}"); coll_success = False; continue
                        # endTryExcept
                    else:
                        logger.debug(f"   Capped collection '{coll_name}' already exists.")
                    # endIfElse
                elif not collection_exists:
                    # Create regular collection implicitly by creating an index, or explicitly if no indexes
                    if not coll_config.get('indexes'):
                        try:
                            logger.info(f"   Collection doesn't exist. Creating empty regular collection '{coll_name}'.")
                            db.create_collection(coll_name)
                            collection_exists = True
                            logger.info(f"   Successfully created empty collection '{coll_name}'.")
                        except pymongo.errors.CollectionInvalid:
                             logger.warning(f"   Regular collection '{coll_name}' already exists (race condition). Proceeding.")
                             collection_exists = True
                        except Exception as e:
                             logger.error(f"   Failed to create empty collection '{coll_name}': {e}"); coll_success = False; continue
                        # endTryExcept
                    else:
                        logger.info(f"   Collection '{coll_name}' doesn't exist. Will be created by first index.")
                    # endIfElse
                # endIfElif

                # --- Index Creation (with compound index support) ---
                defined_indexes = coll_config.get('indexes', [])
                if defined_indexes:
                    logger.info(f"   Ensuring indexes for '{db_name}.{coll_name}'...")
                    try:
                        collection = db[coll_name]
                        for index_def in defined_indexes:
                            index_keys_config = index_def.get('keys')
                            if not index_keys_config or not isinstance(index_keys_config, list):
                                logger.warning(f"     Skipping index in '{coll_name}' due to missing or invalid 'keys' array: {index_def}")
                                continue
                            # endIf

                            index_keys: List[Tuple[str, Union[int, str]]] = []
                            valid_keys = True
                            for key_pair in index_keys_config:
                                if not isinstance(key_pair, list) or len(key_pair) != 2:
                                    logger.error(f"     Invalid key pair format in '{coll_name}'. Expected ['field', 'ORDER']. Got: {key_pair}")
                                    valid_keys = False; break
                                # endIf
                                field_name, order_str = key_pair
                                pymongo_order = INDEX_ORDER_MAP.get(order_str.upper())
                                if pymongo_order is None:
                                    logger.error(f"     Invalid index order '{order_str}' for field '{field_name}' in '{coll_name}'.")
                                    valid_keys = False; break
                                # endIf
                                index_keys.append((field_name, pymongo_order))
                            # endFor
                            
                            if not valid_keys:
                                continue
                            # endIf
                            
                            index_options = {k: v for k, v in index_def.items() if k not in ['keys', 'expire_after_seconds']}
                            if 'expire_after_seconds' in index_def:
                                index_options['expireAfterSeconds'] = index_def['expire_after_seconds']
                            # endIf
                            index_options.setdefault('background', True)
                            index_name = index_options.get('name')

                            logger.info(f"     Ensuring index '{index_name or 'auto'}' on key(s): {index_keys}")
                            collection.create_index(index_keys, **index_options)
                        # endFor
                        logger.debug(f"   Finished index check for '{db_name}.{coll_name}'.")
                    except pymongo.errors.OperationFailure as e:
                        logger.error(f"   Failed to create index for '{db_name}.{coll_name}': {e}", exc_info=True); coll_success = False
                    except Exception as e:
                        logger.error(f"   An unexpected error occurred during index creation for '{db_name}.{coll_name}': {e}", exc_info=True); coll_success = False
                    # endTryExcept
                else:
                    logger.debug(f"   No indexes defined for '{db_name}.{coll_name}'.")
                # endIfElse

                if not coll_success:
                    db_success = False
                # endIf
            # endFor
        except Exception as e:
            logger.error(f"Failed processing database definition '{db_name}': {e}", exc_info=True)
            db_success = False
        # endTryExcept

        if not db_success:
            overall_success = False
        # endIf
    # endFor

    logger.info(f"--- Schema Enforcement Finished for environment: '{environment}' ---")
    return overall_success
# endDef


# --- Main Execution ---

def main():
    parser = argparse.ArgumentParser(description="Apply MongoDB schema or delete specified items.")
    # ... (all parser.add_argument calls remain the same) ...
    parser.add_argument("--action", choices=['apply', 'delete-collections', 'delete-databases'], default='apply', help="Action to perform.")
    parser.add_argument("--client-config", default="mongo_client.json", help="Path to the MongoDB client connection JSON file.")
    parser.add_argument("--schema-config", default="mongo_schema.json", help="Path to the MongoDB schema definition JSON file.")
    parser.add_argument("--env", default=None, help="Specify the environment to use.")
    parser.add_argument("--collections", nargs='+', default=[], help="List of collections (db.coll) for 'delete-collections' action.")
    parser.add_argument("--databases", nargs='+', default=[], help="List of database names for 'delete-databases' action.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.getLogger().setLevel(log_level)
    logger.setLevel(log_level)
    logging.getLogger("mongo_client_manager").setLevel(log_level)
    logger.debug("Debug logging enabled.")

    if args.action == 'apply':
        if args.collections or args.databases:
            logger.warning("Ignoring --collections and --databases arguments when action is 'apply'.")
        # endIf
    elif args.action == 'delete-collections':
        if not args.collections:
            parser.error("Action 'delete-collections' requires the --collections argument.")
        # endIf
        if args.databases:
            parser.error("Cannot provide --databases when action is 'delete-collections'.")
        # endIf
    elif args.action == 'delete-databases':
        if not args.databases:
            parser.error("Action 'delete-databases' requires the --databases argument.")
        # endIf
        if args.collections:
            parser.error("Cannot provide --collections when action is 'delete-databases'.")
        # endIf
    # endIfElifElse

    operation_successful = False
    try:
        logger.info(f"Connecting to MongoDB using client config: {args.client_config}")
        manager = MongoManager(config_path=args.client_config)
        
        # Note: This logic for overriding environment is simplified.
        # A robust solution might involve re-initializing the manager.
        if args.env and manager.environment != args.env:
             logger.warning(f"Overriding environment for manager. Initial: '{manager.environment}', Using: '{args.env}'")
        # endIf

        client = manager.get_client()
        connection_environment = manager.environment
        logger.info(f"Connection established for environment: '{connection_environment}'")

        target_environment = args.env if args.env else manager.environment
        logger.info(f"Target environment for action '{args.action}': '{target_environment}'")

        if args.action == 'apply':
            operation_successful = apply_schema(client, args.schema_config, target_environment)
        elif args.action == 'delete-collections':
            operation_successful = delete_collections(client, args.collections)
        elif args.action == 'delete-databases':
            operation_successful = delete_databases(client, args.databases)
        # endIfElifElse

        if operation_successful:
             logger.info(f"Action '{args.action}' completed successfully.")
        else:
             logger.error(f"Action '{args.action}' completed with errors.")
        # endIfElse

    except (FileNotFoundError, json.JSONDecodeError, ValueError, KeyError) as e:
        logger.critical(f"Configuration or Argument Error: {e}", exc_info=True)
        exit(1)
    except (pymongo.errors.ConnectionFailure, ConnectionError) as e:
        logger.critical(f"MongoDB Connection Error: {e}", exc_info=True)
        exit(1)
    except Exception as e:
        logger.critical(f"An unexpected error occurred: {e}", exc_info=True)
        exit(1)
    # endTryExcept

    exit(0 if operation_successful else 1)
# endDef

if __name__ == "__main__":
    main()
# endIf
