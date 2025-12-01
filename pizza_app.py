from abc import ABC, abstractmethod
from functools import wraps
import threading
import tkinter as tk
from tkinter import messagebox
import asyncio
import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, String, Float  # ORM для работы с БД
from sqlalchemy.orm import sessionmaker  # Класс для создания сессии работы с БД


def log_method_call(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        return func(self, *args, **kwargs)

    return wrapper


class AbstractPizza(ABC):

    @abstractmethod
    def prepare(self) -> None:
        pass

    @abstractmethod
    def __gt__(self, other) -> bool:
        pass

    @abstractmethod
    def __lt__(self, other) -> bool:
        pass


class Topping:

    def __init__(self, name: str, price: int):
        self._name = name
        self._price = price

    def __str__(self) -> str:
        return f"{self._name} ({self._price} руб)"


class PizzaMixin:

    def __init__(self, size: str, topping: Topping, price: int, name: str):
        self._size = size
        self._topping = topping
        self._price = price
        self._name = name

    @property
    def size(self) -> str:
        return self._size

    @property
    def topping(self) -> Topping:
        return self._topping

    @property
    def price(self) -> int:
        return self._price

    @property
    def name(self) -> str:
        return self._name


class Pizza(AbstractPizza, PizzaMixin):

    def __init__(self, size: str, topping: Topping, price: int, name: str):
        super().__init__(size, topping, price, name)

    @log_method_call
    def prepare(self) -> None:
        size_prices = {'S': 150, 'M': 200, 'L': 250}
        print("Введите размер пиццы: (S/M/L) ")
        size = input()
        if size in size_prices:
            self._size = size
            self._price += size_prices[size]
            print(f"Готовится {self._size} {self._name} пицца. Цена: {self._price}.")
        else:
            raise InvalidSize("Некорректный размер пиццы")

    def __gt__(self, other) -> bool:
        return self._price > other._price

    def __lt__(self, other) -> bool:
        return self._price < other._price


class PepperoniPizza(Pizza):

    def __init__(self, size: str):
        topping = Topping("колбаса", 230)
        super().__init__(size, topping, 100, 'Пепперони')

    def preparePepper(self):
        print(f"Добавляем {self.topping} на пиццу Пепперони")


class BBQPizza(Pizza):

    def __init__(self, size: str):
        topping = Topping('острый соус', 240)
        super().__init__(size, topping, 150, 'Барбекю')

    def prepareBBQ(self):
        print(f"Добовляем {self.topping} в пиццу Барбекю")


class SeaPizza(Pizza):

    def __init__(self, size: str):
        topping = Topping('морепродукты', 250)
        super().__init__(size, topping, 200, 'Дары Моря')

    def prepareSea(self):
        print(f"Добавляем {self.topping} на пиццу Дары Моря")


class Order:

    def __init__(self, pizza: Pizza, customer_name: str):
        self._pizza = pizza
        self._customer_name = customer_name

    @property
    def pizza(self):
        return self._pizza

    @property
    def customer_name(self):
        return self._customer_name


class InvalidSize(Exception):

    def __init__(self, message: str):
        self.message = message


class InvalidTop(Exception):

    def __init__(self, message: str):
        self.message = message


class InvalidPizza(Exception):

    def __init__(self, message: str):
        self.message = message


# Класс Base определяет базовый класс для объектов ORM SQLAlchemy
Base = sqlalchemy.orm.declarative_base()


# Класс PizzaOrder представляет таблицу в базе данных, в которой хранятся заказы пиццы
class PizzaOrder(Base):
    __tablename__ = 'pizza_orders'
    id = Column(Integer, primary_key=True)
    pizza_name = Column(String)
    pizza_size = Column(String)
    pizza_price = Column(Float)
    customer_name = Column(String)

    def __repr__(self):
        return (f"PizzaOrder(pizza_name='{self.pizza_name}', pizza_size='{self.pizza_size}', "
                f"pizza_price={self.pizza_price}, customer_name='{self.customer_name}')")


class Terminal:

    def __init__(self):
        self.menu = {
            "Пепперони": PepperoniPizza(size='S'),
            "Барбекю": BBQPizza(size='S'),
            "Дары Моря": SeaPizza(size='S')
        }
        self.lock = threading.Lock()
        self.engine = create_engine('sqlite:///pizza_orders.db')
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.Session = Session()

    @log_method_call
    def display_menu(self):
        print("Меню")
        for name, pizza in self.menu.items():
            print(f"{pizza.name}: {pizza.size} размер, начинка {pizza.topping}")

    @log_method_call
    async def take_order(self):
        try:
            self.display_menu()
            order = input("Какую пиццу вы хотите заказать? ")
            if order in self.menu:
                pizza = self.menu[order]
                pizza.prepare()
                top = input("Хотите добавить начинку в пиццу? ")
                if top == 'да':
                    if isinstance(pizza, PepperoniPizza):
                        pizza.preparePepper()
                    elif isinstance(pizza, SeaPizza):
                        pizza.prepareSea()
                    elif isinstance(pizza, BBQPizza):
                        pizza.prepareBBQ()
                elif top == 'нет':
                    print("Пицца без начинки")

                for name, p in self.menu.items():
                    if p != pizza and p.price < pizza.price:
                        print(f"{name} дешевле чем {order}")
                customer_name = input("Введите ваше имя: ")
                order = Order(pizza, customer_name)

                # создаем задачу для обработки заказа
                task = asyncio.create_task(self.confirm_order(order))
                await task  # ожидаем выполнения задачи

            else:
                raise InvalidPizza("Такой пиццы нет в меню")

        except Exception as e:
            print(e)

    @log_method_call
    async def confirm_order(self, order: Order):
        with self.lock:  # используем блокировку для синхронизации
            new_order = PizzaOrder(pizza_name=order.pizza.name, pizza_size=order.pizza.size,
                                   pizza_price=order.pizza.price, customer_name=order.customer_name)
            self.Session.add(new_order)
            self.Session.commit()
            print(
                f"Ваш заказ: {order.pizza.name} {order.pizza.size} размер, цена: {order.pizza.price} ")
            customer_name = order.customer_name
            print(f"Спасибо, {customer_name} за заказ!")


class GUI(tk.Tk, Terminal):
    def __init__(self, terminal):
        super().__init__()
        self.title("Заказ пиццы")
        self.terminal = terminal
        self.create_widgets()

    def create_widgets(self):
        self.menu_label = tk.Label(self, text="Выберите пиццу:")
        self.menu_label.pack()

        self.menu_var = tk.StringVar()
        self.menu_dropdown = tk.OptionMenu(self, self.menu_var, *self.terminal.menu.keys())
        self.menu_dropdown.pack()

        self.top_label = tk.Label(self, text="Хотите добавить начинку?")
        self.top_label.pack()

        self.top_var = tk.StringVar()
        self.top_checkbox = tk.Checkbutton(self, variable=self.top_var, text="Да")
        self.top_checkbox.pack()

        self.name_label = tk.Label(self, text="Введите ваше имя:")
        self.name_label.pack()

        self.name_entry = tk.Entry(self)
        self.name_entry.pack()

        self.order_button = tk.Button(self, text="Заказать", command=self.take_order)
        self.order_button.pack()

    def place_order(self):
        order = self.menu_var.get()
        if order not in self.terminal.menu:
            messagebox.showerror("Ошибка: Такой пиццы нет в меню")
            return

        pizza = self.terminal.menu[order]
        pizza.prepare()

        if self.top_var.get() == "1":
            if isinstance(pizza, PepperoniPizza):
                pizza.preparePepper()
            elif isinstance(pizza, SeaPizza):
                pizza.prepareSea()
            elif isinstance(pizza, BBQPizza):
                pizza.prepareBBQ()

        customer_name = self.name_entry.get()
        order = Order(pizza, customer_name)

        self.terminal.confirm_order(order)
        messagebox.showinfo("Спасибо", f"Спасибо, {customer_name} за заказ!")


terminal = Terminal()
gui = GUI(terminal)
gui.mainloop()
gui.terminal("100x100")
gui.terminal(width=False, height=False)
while True:
    asyncio.run(terminal.take_order())
    choice = input("Хотите заказать еще? (да/нет) ")
    if choice != 'да':
        break
