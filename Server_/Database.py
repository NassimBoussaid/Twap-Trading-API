from sqlalchemy import create_engine, Column, String, Float, Integer, ForeignKey, PrimaryKeyConstraint, Enum, DateTime, \
    func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from passlib.context import CryptContext

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
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    symbol = Column(String, nullable=False)
    side = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    status = Column(Enum("pending", "executing", "completed", "canceled", name="order_status_enum"), nullable=False,
                    default="pending")
    created_at = Column(DateTime, default=func.now())


class TwapExecution(Base):
    __tablename__ = "twap_executions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("twap_orders.id", ondelete="CASCADE"), nullable=False)
    executed_quantity = Column(Float, nullable=False)  # Quantité exécutée à chaque intervalle
    execution_price = Column(Float, nullable=False)
    exchange = Column(String, nullable=False)
    timestamp = Column(DateTime, default=func.now())


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

    def add_twap_order(self, user_id: int, symbol: str, side: str, quantity: float, price: float):
        session = self.SessionLocal()
        try:
            new_order = Twap(
                user_id=user_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                status="pending",
                created_at=func.now()
            )
            session.add(new_order)
            session.commit()
            session.refresh(new_order)
            return new_order
        except SQLAlchemyError as e:
            session.rollback()
            raise Exception(f"Error adding TWAP order: {e}")

    def get_twap_orders(self, user_id: int):
        session = self.SessionLocal()
        return session.query(Twap).filter(Twap.user_id == user_id).all()

    def get_twap_order_by_id(self, order_id: int):
        session = self.SessionLocal()
        order = session.query(Twap).filter(Twap.id == order_id).first()
        if not order:
            raise Exception(f"Order ID {order_id} not found")
        return order

    def update_twap_order_status(self, order_id: int, new_status: str):
        session = self.SessionLocal()
        valid_status = ["pending", "executing", "completed", "canceled"]
        if new_status not in valid_status:
            raise ValueError(f"Invalid status '{new_status}', must be one of {valid_status}")

        order = session.query(Twap).filter(Twap.id == order_id).first()
        if not order:
            raise Exception(f"Order ID {order_id} not found")

        order.status = new_status
        session.commit()
        session.refresh(order)
        return order

    def close_twap_order(self, order_id: int, canceled: bool = False):
        session = self.SessionLocal()
        order = session.query(Twap).filter(Twap.id == order_id).first()
        if not order:
            raise Exception(f"Order ID {order_id} not found")

        order.status = "canceled" if canceled else "completed"
        session.commit()
        session.refresh(order)
        return order

    def add_twap_execution(self, order_id: int, executed_quantity: float, execution_price: float, exchange: str):
        session = self.SessionLocal()
        try:
            execution = TwapExecution(
                order_id=order_id,
                executed_quantity=executed_quantity,
                execution_price=execution_price,
                exchange=exchange,
                timestamp=func.now()
            )
            session.add(execution)
            session.commit()
            session.refresh(execution)
            return execution
        except SQLAlchemyError as e:
            session.rollback()
            raise Exception(f"Error adding TWAP execution: {e}")

    def get_twap_executions(self, order_id: int):
        session = self.SessionLocal()
        return session.query(TwapExecution).filter(TwapExecution.order_id == order_id).all()


database_api = Database()
