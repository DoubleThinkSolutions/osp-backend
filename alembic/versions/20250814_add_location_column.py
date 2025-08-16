"""Add location column and migrate lat/lng to location

Revision ID: add_location_column
Revises: eb6845fcc5c9
Create Date: 2025-08-14 19:14:00.000000

"""
from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geography

# revision identifiers, used by Alembic.
revision = 'add_location_column'
down_revision = 'eb6845fcc5c9'
branch_labels = None
depends_on = None

def upgrade():
    # 1. Enable PostGIS extension (required for geography type)
    op.execute('CREATE EXTENSION IF NOT EXISTS postgis;')
    
    # 2. Add the new location column (PostGIS Geography type)
    op.add_column('media', 
        sa.Column('location', Geography(geometry_type='POINT', srid=4326), nullable=True)
    )
    
    # 3. Populate location from existing lat/lng
    op.execute("""
        UPDATE media
        SET location = ST_SetSRID(ST_MakePoint(lng::double precision, lat::double precision), 4326)::geography
        WHERE lng IS NOT NULL AND lat IS NOT NULL;
    """)
    
    # 4. Optionally, set location column to NOT NULL if all rows have lat/lng
    # Comment out if you have rows without lat/lng data
    op.alter_column('media', 'location', nullable=False)
    
    # 5. Optional: drop old lat/lng columns if no longer needed
    # Comment out if you want to keep them for compatibility
    op.drop_column('media', 'lat')
    op.drop_column('media', 'lng')

def downgrade():
    # 1. Add lat/lng columns back
    op.add_column('media', sa.Column('lat', sa.Float, nullable=True))
    op.add_column('media', sa.Column('lng', sa.Float, nullable=True))
    
    # 2. Populate lat/lng from location
    op.execute("""
        UPDATE media
        SET lat = ST_Y(location::geometry),
            lng = ST_X(location::geometry)
        WHERE location IS NOT NULL;
    """)
    
    # 3. Drop location column
    op.drop_column('media', 'location')