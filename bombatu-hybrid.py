class PKPIAppDynamicsMotorRepository(
    BaseReadMotorRepository[PlatformMetricDocument],
    BaseWriteMotorRepository[PlatformMetricDocument]
):
    """
    Repository for Platform KPI appdynamics collection in MongoDB.
    Provides methods for reading and writing alert documents,
    including finding, creating, and updating alerts.
    """

    _collection_name = DatabasesCollections.PLATFORM_KPI_APPDYNAMICS_COLLECTION
    _database_name = DatabasesCollections.PLATFORM_KPI_DATABASE

    async def find_one(
        self,
        filter_query: MotorDocument,
        projection: MotorDocument | None = None,
        sort_options: list[tuple[str, int]] | None = None,
        collation: Collation | None = None,
    ) -> PlatformMetricDocument | None:
        ...

async def get_pkpi_appdynamics_repository(
    db_client: AsyncIOMotorClient,
) -> PKPIAppDynamicsMotorRepository:
    """
    Dependency injection function to get an instance of PKPIAppDynamicsMotorRepository.

    :param db_client: The MongoDB client instance.
    :type db_client: AsyncIOMotorClient
    :return: An instance of PKPIAppDynamicsMotorRepository.
    :rtype: PKPIAppDynamicsMotorRepository
    """

    return PKPIAppDynamicsMotorRepository(db_client, PlatformMetricDocument)
    
    
    
class BaseWriteMotorRepository[T](ABC):
    """Similar init like the read class"""

    def write_map_to_model(self, doc: MongoDocument) -> T:
        """
        Maps a MongoDB document to the model type T.
        This method converts the document to a Pydantic model,
        handling ObjectId conversion for the _id field.

        :param doc: The MongoDB document to map.
        :type doc: MongoDocument
        :return: An instance of type T.
        :rtype: T
        """
        return self._base_model(**doc)

    @staticmethod
    def write_map_to_document(model: T) -> MongoDocument:
        """
        Maps the model type T to a MongoDB document.
        This method converts the model to a dictionary and ensures
        that the _id field is an ObjectId if present.

        :param model: The model instance to map.
        :type model: T
        :return: A MongoDB document representation of the model.
        :rtype: MongoDocument
        """

        # Pydantic v2: model_dump instead of dict
        doc = model.model_dump(by_alias=True, exclude_none=True)

        # Ensure _id is ObjectId if present
        if "_id" in doc and doc["_id"] is not None and not isinstance(doc["_id"], bson.ObjectId):
            doc["_id"] = bson.ObjectId(doc["_id"])
        elif "_id" in doc and doc["_id"] is None:
            # Remove if id was None and became _id: None
            del doc["_id"]

        return doc


class BaseDeleteMotorRepository[T](ABC):
    """Similar init like the read class"""

    def delete_map_to_model(self, doc: MongoDocument) -> T:
        ...

    @staticmethod
    def delete_map_to_document(model: T) -> MongoDocument:
        ...