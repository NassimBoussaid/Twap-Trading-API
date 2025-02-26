import datetime

from sqlalchemy import create_engine, Column, String, Float, Integer, ForeignKey, PrimaryKeyConstraint, Enum, DateTime, \
    func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from passlib.context import CryptContext
from typing import Dict, List

DATABASE_URL = "sqlite:///api_database.db"

# Connexion à SQLite
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

Base = declarative_base()


# Modèle User pour la base de données
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, unique=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False)


class Twap(Base):
    __tablename__ = "twap_orders"
    id = Column(Integer, primary_key=True,autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    symbol = Column(String, nullable=False)
    exchange = Column(String, nullable=False)
    side = Column(String, nullable=False)
    avg_executed_price = Column(Float,nullable=False)
    executed_quantity = Column(Float, nullable=False)
    duration = Column(Float,nullable=False)
    status = Column(Enum("pending", "executing", "completed", "canceled", name="order_status_enum"), nullable=False,
                    default="pending")
    created_at = Column(DateTime, default=func.now())


class TwapExecution(Base):
    __tablename__ = "twap_executions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("twap_orders.id", ondelete="CASCADE"), nullable=False)
    symbol = Column(String, nullable=False)
    side = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    timestamp = Column(String, nullable=False)


# Créer les tables dans la base de données
Base.metadata.create_all(bind=engine)


class Database:
    def __init__(self):
        self.SessionLocal = SessionLocal

    def retrieve_user_by_username(self, username: str):
        session = self.SessionLocal()
        try:
            return session.query(User).filter(User.username == username).first()
        finally:
            session.close()

    def retrieve_pwd_by_username(self, username: str):
        user = self.retrieve_user_by_username(username)
        return user.password if user else None

    def retrieve_role_by_username(self, username: str):
        user = self.retrieve_user_by_username(username)
        return user.role if user else None

    def create_user(self, username: str, password: str):
        session = self.SessionLocal()
        try:
            # hashed_password = pwd_context.hash(password)
            user = User(username=username, password=password, role="user")
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

    def delete_user(self, username: str):
        session = self.SessionLocal()
        try:
            user = session.query(User).filter(User.username == username).first()
            if user:
                session.delete(user)
            session.commit()
        finally:
            session.close()


    def add_order_executions(self, order_id : str,symbol: str,executions: List[Dict]):
        session = self.SessionLocal()
        try:
            for execution in executions:
                new_order = TwapExecution(
                    order_id=order_id,
                    symbol=symbol,
                    side=execution["side"],
                    quantity=execution["quantity"],
                    price=execution["price"],
                    timestamp=execution.get("timestamp")
                )
                session.add(new_order)

            session.commit()
            return "Orders successfully added"
        except SQLAlchemyError as e:
            session.rollback()
            raise Exception(f"Error adding TWAP orders: {e}")
        finally:
            session.close()

    def add_order(self,username: str,token_id:str,symbol:str,exchange:str,side:str,executed_price:float,executed_quantity:float,executed_duration:float,status:str):
        session = self.SessionLocal()
        try:
            existing_order = session.query(Twap).filter(Twap.id == token_id).first()
            user = self.retrieve_user_by_username(username)
            if existing_order:
                raise HTTPException(status_code=400, detail="Order ID already exists")
            new_order = Twap(
                id=token_id,
                user_id=user.id,
                symbol=symbol,
                exchange = exchange,
                side=side,
                avg_executed_price = executed_price,
                executed_quantity=executed_quantity,
                duration=executed_duration,
                status=status,
                created_at = func.now()
            )
            session.add(new_order)
            session.commit()
        except Exception as e:
            session.rollback()
            raise HTTPException(status_code=500, detail=f"Error creating order: {e}")
        finally:
            session.close()

    def get_orders(self, order_id : str = None):
        session = self.SessionLocal()
        try:
            query = session.query(Twap)
            if order_id:
                query = query.filter(Twap.id == order_id)
            orders = query.all()
            results = []
            for order in orders:
                results.append({
                    "order_id": order.id,
                    "user_id":order.user_id,
                    "symbol": order.symbol,
                    "exchange": order.exchange,
                    "side":order.side,
                    "avg_executed_price": order.avg_executed_price,
                    "executed_quantity": order.executed_quantity,
                    "duration":order.duration,
                    "status":order.status,
                    "created_at":order.created_at
                })
            return results
        finally:
            session.close()

    def get_orders_executions(self,order_id : str = None,symbol: str = None, side: str = None):
        session = self.SessionLocal()
        try:
            query = session.query(TwapExecution)
            if symbol:
                query = query.filter(TwapExecution.symbol == symbol)
            if order_id:
                query = query.filter(TwapExecution.order_id == order_id)
            if side:
                query = query.filter(TwapExecution.side == side)
            executions = query.all()
            results = []
            for execution in executions:
                results.append({
                    "id" : execution.id,
                    "order_id": execution.order_id,
                    "symbol": execution.symbol,
                    "side":execution.side,
                    "quantity":execution.quantity,
                    "price":execution.price,
                    "timestamp":execution.timestamp
                })
            return results
        finally:
            session.close()


database_api = Database()
