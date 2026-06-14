from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.database import Base
from app.models import *
config = context.config
if config.config_file_name: fileConfig(config.config_file_name)
target_metadata = Base.metadata

def run_offline():
    context.configure(url=config.get_main_option('sqlalchemy.url'), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction(): context.run_migrations()

def run_online():
    c = engine_from_config(config.get_section(config.config_ini_section), prefix='sqlalchemy.', poolclass=pool.NullPool)
    with c.connect() as conn:
        context.configure(conn=conn, target_metadata=target_metadata)
        with context.begin_transaction(): context.run_migrations()

run_offline() if context.is_offline_mode() else run_online()
