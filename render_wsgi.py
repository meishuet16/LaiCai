from retaniq.api import create_app
from retaniq.database_config import DatabaseConfig

application = create_app(DatabaseConfig.from_environment())
