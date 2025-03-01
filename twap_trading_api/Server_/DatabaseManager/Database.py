from sqlalchemy import create_engine, Column, String, Float, Integer, ForeignKey, Enum, DateTime, \
    func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from passlib.context import CryptContext
from typing import Dict, List
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Récupère le chemin du fichier actuel
DATABASE_PATH = os.path.join(BASE_DIR, "api_database.db")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# Connection to SQLite
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

Base = declarative_base()


class User(Base):
    """
        User class for database management
    """
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, unique=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False)


class Twap(Base):
    """
        Twap Orders class for database management
    """
    __tablename__ = "twap_orders"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    symbol = Column(String, nullable=False)
    exchange = Column(String, nullable=False)
    side = Column(String, nullable=False)
    limit_price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    duration = Column(Float, nullable=False)
    status = Column(Enum("pending", "executing", "completed", "canceled", name="order_status_enum"), nullable=False,
                    default="pending")
    created_at = Column(DateTime, default=func.now())

    percent_exec = Column(Float, default=0.0)
    avg_exec_price = Column(Float, default=0.0)
    lots_count = Column(Integer, default=0)
    total_exec = Column(Float, default=0.0)


class TwapExecution(Base):
    """
        Twap exections class for database management
    """
    __tablename__ = "twap_executions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("twap_orders.id", ondelete="CASCADE"), nullable=False)
    symbol = Column(String, nullable=False)
    side = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    exchange = Column(String, nullable=False)
    timestamp = Column(String, nullable=False)


# Créer les tables dans la base de données
Base.metadata.create_all(bind=engine)


class Database:
    """
        Database class for defining database methods and attributes.
        This class provides various methods to interact with the database, including
        user management and TWAP order processing.
    """

    def __init__(self):
        """
            Initialize the Database instance with a session factory.
        """
        self.SessionLocal = SessionLocal

    def retrieve_user_by_username(self, username: str):
        """
            Retrieve user in the database by username

            Arg:
                username (str): username to retrieve user

            Return:
                User: The corresponding user instance if found, else None
        """
        session = self.SessionLocal()
        try:
            return session.query(User).filter(User.username == username).first()
        finally:
            session.close()

    def retrieve_pwd_by_username(self, username: str):
        """
            Retrieve a user's password from the database by username.

            Args:
                username (str): The username to look up.

            Returns:
                str: The password of the user if found, otherwise None.
        """
        user = self.retrieve_user_by_username(username)
        return user.password if user else None

    def retrieve_role_by_username(self, username: str):
        """
            Retrieve a user's role from the database by username.

            Args:
                username (str): The username to look up.

            Returns:
                str: The role of the user if found, otherwise None.
        """
        user = self.retrieve_user_by_username(username)
        return user.role if user else None

    def create_user(self, username: str, password: str):
        """
            Create a new user in the database.

            Args:
                username (str): The desired username for the new user.
                password (str): The password for the new user.

            Raises:
                SQLAlchemyError: If there is an issue during user creation.
        """
        session = self.SessionLocal()
        try:
            # hashed_password = pwd_context.hash(password)
            user = User(username=username, password=password, role="user")
            session.add(user)
            session.commit()
        finally:
            session.close()

    def retrieve_all_users(self):
        """
            Retrieve all users from the database.

            Returns:
                List[User]: A list of all user instances in the database.
        """
        session = self.SessionLocal()
        try:
            return session.query(User).all()
        finally:
            session.close()

    def delete_user(self, username: str):
        """
            Delete a specified user from the database.

            Args:
                username (str): The username of the user to delete.

            Raises:
                SQLAlchemyError: If an error occurs during the deletion process.
        """
        session = self.SessionLocal()
        try:
            user = session.query(User).filter(User.username == username).first()
            if user:
                session.delete(user)
            session.commit()
        finally:
            session.close()

    def add_order_executions(self, order_id: str, symbol: str, side: str, quantity: float, price: float, exchange: str,
                             timestamp: str):
        """
            Add executions for a specified TWAP order in the database.

            Args:
                order_id (str): The unique identifier of the TWAP order.
                symbol (str): The trading pair symbol (e.g., "BTCUSDT").
                side (str): Order side, either "buy" or "sell".
                price (str): executed price
                timestamp (str): execution time

            Returns:
                str: Confirmation message indicating successful insertion.

            Raises:
                Exception: If an error occurs while adding executions.
        """
        session = self.SessionLocal()
        try:
            new_order = TwapExecution(
                order_id=order_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                exchange=exchange,
                timestamp=timestamp
            )
            session.add(new_order)

            session.commit()
            return "Orders successfully added"
        except SQLAlchemyError as e:
            session.rollback()
            raise Exception(f"Error adding TWAP orders: {e}")
        finally:
            session.close()

    def add_order(self, username: str, order_id: str, symbol: str, exchange: str, side: str, limit_price: float,
                  quantity: float, executed_duration: float, status: str):
        """
            Add a new TWAP order to the database.

            Args:
                username (str): Username of the user placing the order.
                order_id (str): Unique identifier for the order.
                symbol (str): Trading pair symbol (e.g., "BTCUSDT").
                exchange (str): Exchange where the order is executed.
                side (str): Order side, either "buy" or "sell".
                limit_price (float): Average execution price of the order.
                quantity (float): Total executed quantity.
                executed_duration (float): Duration of the order execution.
                status (str): Current status of the order.

            Raises:
                HTTPException: If the order ID already exists or if an error occurs while creating the order.
        """
        session = self.SessionLocal()
        try:
            existing_order = session.query(Twap).filter(Twap.id == order_id).first()
            user = self.retrieve_user_by_username(username)
            if existing_order:
                raise HTTPException(status_code=400, detail="Order ID already exists")
            new_order = Twap(
                id=order_id,
                user_id=user.id,
                symbol=symbol,
                exchange=exchange,
                side=side,
                limit_price=limit_price,
                quantity=quantity,
                duration=executed_duration,
                status=status,
                created_at=func.now()
            )
            session.add(new_order)
            session.commit()
        except Exception as e:
            session.rollback()
            raise HTTPException(status_code=500, detail=f"Error creating order: {e}")
        finally:
            session.close()

    def get_orders(self, user_id: int,order_id: str = None):
        """
            Retrieve orders from the database.

            Args:
                order_id (str, optional): Specific order ID to retrieve (default: None).
                user_id (int): Specific user id to retrieve his orders

            Returns:
                List[Dict]: A list of orders with their details.
        """
        session = self.SessionLocal()
        try:
            query = session.query(Twap).filter(Twap.user_id == user_id)
            if order_id:
                query = query.filter(Twap.id == order_id)
            orders = query.all()
            results = []
            if not orders:
                raise HTTPException(status_code=404, detail="No orders found")
            for order in orders:
                results.append({
                    "order_id": order.id,
                    "user_id": order.user_id,
                    "symbol": order.symbol,
                    "exchange": order.exchange,
                    "side": order.side,
                    "limit_price": order.limit_price,
                    "quantity": order.quantity,
                    "duration": order.duration,
                    "status": order.status,
                    "created_at": order.created_at,
                    "percent_exec": order.percent_exec,
                    "avg_exec_price": order.avg_exec_price,
                    "lots_count": order.lots_count,
                    "total_exec": order.total_exec
                })
            return results
        finally:
            session.close()

    def get_orders_executions(self, user_id: int, order_id: str, symbol: str = None, side: str = None):
        """
            Retrieve execution details of TWAP orders for a specific user.

            Args:
                user_id (int): ID of the user requesting executions.
                order_id (str, optional): Order ID to filter executions (default: None).
                symbol (str, optional): Trading pair symbol to filter executions (default: None).
                side (str, optional): Order side ("buy" or "sell") to filter executions (default: None).

            Returns:
                List[Dict]: A list of executions matching the given filters.
        """
        session = self.SessionLocal()
        try:
            # Check that the order matches the user if user_id is given
            if order_id:
                order = session.query(Twap).filter(Twap.id == order_id, Twap.user_id == user_id).first()
                if not order:
                    raise HTTPException(status_code=404, detail="Order not found or unauthorized")

            # Building request to retrieve executions
            query = session.query(TwapExecution).join(Twap, TwapExecution.order_id == Twap.id).filter(
                Twap.user_id == user_id)

            if order_id:
                query = query.filter(TwapExecution.order_id == order_id)
            if symbol:
                query = query.filter(TwapExecution.symbol == symbol)
            if side:
                query = query.filter(TwapExecution.side == side)

            executions = query.all()

            if not executions:
                raise HTTPException(status_code=404, detail="No executions found matching the criteria")

            results = [{
                "id": execution.id,
                "order_id": execution.order_id,
                "symbol": execution.symbol,
                "side": execution.side,
                "quantity": execution.quantity,
                "price": execution.price,
                "exchange": execution.exchange,
                "timestamp": execution.timestamp
            } for execution in executions]

            return results

        finally:
            session.close()

    def update_order_status(self, order_id: str, new_status: str):
        """
            Updates the status of an order in the database.

            Args:
                order_id (str): The unique identifier of the order to be updated.
                new_status (str): The new status to assign to the order.

            Behavior:
                - Searches for the order with `order_id` in the database.
                - If the order exists, updates its status to `new_status` and commits the change.
                - In case of an error, rolls back the transaction and prints an error message.

            Exceptions:
                - Catches any exceptions that occur during the update process and displays an error message.
        """
        session = self.SessionLocal()
        try:
            order = session.query(Twap).filter(Twap.id == order_id).first()
            if order:
                order.status = new_status
                session.commit()
        except Exception as e:
            session.rollback()
            print(f"Error updating order status: {e}")
        finally:
            session.close()

    def update_order_state(self, order_id: str, state: Dict):
        """
            Updates the detailed information of a TWAP order in the database.

            The `state` dictionary must contain the following keys:
                - status
                - percentage_executed
                - vwap
                - avg_execution_price
                - lots_count
                - total_quantity_executed

            Args:
                order_id (str): The unique identifier of the order to update.
                state (Dict): A dictionary containing the new order details.

            Behavior:
                - Searches for the order with `order_id` in the database.
                - If the order exists, updates its attributes with values from `state`.
                - Uses `.get()` to preserve existing values if a key is missing.
                - Commits the changes to the database.
                - In case of an error, rolls back the transaction and raises an exception.

            Exceptions:
                - Raises an exception if an error occurs while updating the order state.
        """
        session = self.SessionLocal()
        try:
            order = session.query(Twap).filter(Twap.id == order_id).first()
            if order:
                order.status = state.get("status", order.status)
                order.percent_exec = state.get("percent_exec", order.percent_exec)
                order.avg_exec_price = state.get("avg_exec_price", order.avg_exec_price)
                order.lots_count = state.get("lots_count", order.lots_count)
                order.total_exec = state.get("total_exec", order.total_exec)
                session.commit()
        except Exception as e:
            session.rollback()
            raise Exception("Error updating order state: " + str(e))
        finally:
            session.close()


database_api = Database()
