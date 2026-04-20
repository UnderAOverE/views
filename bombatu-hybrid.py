class BaseReadMotorRepository(T)(ABC):
    """
    BaseReadMotorRepository class: This is a base read repository for MongoDB collections using Motor.
    It provides methods to perform ONLY read operations on MongoDB collections. Subclasses must define the _collection_name and _database_name attributes.
    """

    _database_name: str
    _collection_name: str

    def __init__(self, db_client: AsyncIOMotorClient, base_model: type[T],) -> None:
        """
        MotorRepository constructor. Base repository for MongoDB (Motor) collections. Make sure the inheriting class defines _collection_name and _database_name.

        :param db_client: MongoDB client.
        :type db_client: AsyncIOMotorClient
        :param base_model: The Pydantic model class representing the documents in the collection.
        :type base_model: type[T]
        :return: None
        :raises NotImplementedError: If the subclass does not define _collection_name or _database_name.
        """

        if not hasattr(self, "_collection_name") or not self._collection_name:
            raise NotImplementedError("Subclasses must define _collection_name")

        # endif

        if not hasattr(self, "_database_name") or not self._database_name:
            raise NotImplementedError("Subclasses must define _database_name")

        # endif

        self.db_client: AsyncIOMotorClient = db_client
        self.collection: AsyncIOMotorCollection = db_client[self._database_name][self._collection_name]
        self.base_model = base_model

    # endDef

    def _read_map_to_model(self, doc: MongoDocument,) -> T:


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