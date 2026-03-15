import sys
import os
sys.path.append(os.getcwd())
from models import Base
print("Tables in Metadata:", Base.metadata.tables.keys())
