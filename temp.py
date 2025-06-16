async def _execute_update_one(self, filter_query: MongoDocument, update_doc: MongoDocument, upsert: bool = False,) -> UpdateResult:
    """
    Executes an update_one operation on the collection.

    :param filter_query: The filter query to find the document to update.
    :param update_doc: The update document containing the changes to apply.
    :param upsert: Whether to insert a new document if no document matches the filter.
    :return: The result of the update operation.
    """
    try:
        return await self._collection.update_one(filter_query, {"$set": update_doc}, upsert=upsert)
    except Exception as generic_exception:
        raise Exception(f"Error in _execute_update_one for {self._collection_name}, exception: {repr(generic_exception)}")

# endTryExcept

# endAsyncDef

async def _execute_update_many(self, filter_query: MongoDocument, update_doc: MongoDocument, upsert: bool = False,) -> UpdateResult:
    """
    Executes an update_many operation on the collection.

    :param filter_query: The filter query to find the documents to update.
    :param update_doc: The update document containing the changes to apply.
    :param upsert: Whether to insert new documents if no documents match the filter.
    :return: The result of the update operation.
    """
    try:
        return await self._collection.update_many(filter_query, {"$set": update_doc}, upsert=upsert)
    except Exception as generic_exception:
        raise Exception(f"Error in _execute_update_many for {self._collection_name}, exception: {repr(generic_exception)}")

# endTryExcept

# endAsyncDef