"""data_loader_factory.py — escolhe automaticamente o backend.

Se DATABASE_URL estiver definido, usa PostgreSQL.
Caso contrário, usa Google Sheets (comportamento anterior).
"""
import os


def get_data_loader(sheets_client=None):
    """Devolve o DataLoader correcto consoante o ambiente."""
    if os.environ.get("DATABASE_URL"):
        from services.data_loader_pg import DataLoader
        return DataLoader()
    else:
        from services.data_loader import DataLoader
        return DataLoader(sheets_client=sheets_client)
