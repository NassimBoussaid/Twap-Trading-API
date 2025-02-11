from sqlalchemy import create_engine, Column, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from passlib.context import CryptContext

DATABASE_URL = "sqlite:///api_database.db"

# Connexion à SQLite
engine = create_engine(DATABASE_URL,pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

Base = declarative_base()

# Modèle User pour la base de données
class User(Base):
    __tablename__ = "users"
    username = Column(String, primary_key=True, unique = True)
    password = Column(String,unique=True,nullable = False)
    role = Column(String, nullable=False)

# Créer les tables dans la base de données
Base.metadata.create_all(bind=engine)

class Database:
    def __init__(self):
        self.SessionLocal = SessionLocal

    def retrieve_user_by_username(self,username:str):
        session = self.SessionLocal()
        try :
            return session.query(User).filter(User.username == username).first()
        finally:
            session.close()

    def retrieve_pwd_by_username(self,username:str):
        user = self.retrieve_user_by_username(username)
        return user.password if user else None

    def retrieve_role_by_username(self,username:str):
        user = self.retrieve_user_by_username(username)
        return user.role if user else None

    def create_user(self, username: str, password: str,role: str):
        session = self.SessionLocal()
        try:
            # hashed_password = pwd_context.hash(password)
            user = User(username=username,password = password, role=role)
            session.add(user)
            session.commit()
        finally:
            session.close()

    def retrieve_all_users(self):
        session = self.SessionLocal()
        try:
            return session.query(User).all()
        finally:
            session.close()

    def delete_user(self,username: str):
        session = self.SessionLocal()
        try:
            user = session.query(User).filter(User.username == username).first()
            session.delete(user)
            session.commit()
        finally:
            session.close()

database_api = Database()