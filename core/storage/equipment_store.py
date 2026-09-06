"""Equipment register store for P&ID tag lookup and reconciliation."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from storage.db import DatabaseManager


@dataclass
class EquipmentRegisterEntry:
    """Master equipment register record."""

    tag_id: str
    unit_id: str
    equipment_name: str
    service_description: str
    design_pressure_mpa: float
    design_temp_c: float
    is_active: bool = True


class EquipmentRegisterStore:
    """Synchronous/async store for querying master equipment/instrument register tags."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_manager = DatabaseManager(self.db_path)

    async def add_equipment_entry(self, entry: EquipmentRegisterEntry) -> None:
        """Insert or update an equipment register record."""
        async with self.db_manager.connect() as conn:
            await self.db_manager.initialize_schema(conn)
            await conn.execute(
                """
                INSERT INTO equipment_register
                (tag_id, unit_id, equipment_name, service_description, design_pressure_mpa, design_temp_c, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tag_id) DO UPDATE SET
                    unit_id = excluded.unit_id,
                    equipment_name = excluded.equipment_name,
                    service_description = excluded.service_description,
                    design_pressure_mpa = excluded.design_pressure_mpa,
                    design_temp_c = excluded.design_temp_c,
                    is_active = excluded.is_active
                """,
                (
                    entry.tag_id,
                    entry.unit_id,
                    entry.equipment_name,
                    entry.service_description,
                    entry.design_pressure_mpa,
                    entry.design_temp_c,
                    1 if entry.is_active else 0,
                ),
            )
            await conn.commit()

    async def get_all_tags(self) -> list[EquipmentRegisterEntry]:
        """Fetch all active equipment register tags."""
        async with self.db_manager.connect() as conn:
            await self.db_manager.initialize_schema(conn)
            cursor = await conn.execute(
                "SELECT tag_id, unit_id, equipment_name, service_description, design_pressure_mpa, design_temp_c, is_active FROM equipment_register WHERE is_active = 1"
            )
            rows = await cursor.fetchall()
            return [
                EquipmentRegisterEntry(
                    tag_id=r[0],
                    unit_id=r[1],
                    equipment_name=r[2],
                    service_description=r[3],
                    design_pressure_mpa=r[4],
                    design_temp_c=r[5],
                    is_active=bool(r[6]),
                )
                for r in rows
            ]

    async def lookup_tag(self, tag_id: str) -> EquipmentRegisterEntry | None:
        """Lookup a specific tag ID in the register (exact or normalized match)."""
        clean_tag = tag_id.strip().upper()
        async with self.db_manager.connect() as conn:
            await self.db_manager.initialize_schema(conn)
            cursor = await conn.execute(
                "SELECT tag_id, unit_id, equipment_name, service_description, design_pressure_mpa, design_temp_c, is_active FROM equipment_register WHERE UPPER(tag_id) = ?",
                (clean_tag,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return EquipmentRegisterEntry(
                tag_id=row[0],
                unit_id=row[1],
                equipment_name=row[2],
                service_description=row[3],
                design_pressure_mpa=row[4],
                design_temp_c=row[5],
                is_active=bool(row[6]),
            )
