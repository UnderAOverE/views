# Pytest and Test Coverage Example: Shopping Cart

This project provides a complete, practical example of testing a Python class using `pytest` and measuring the test coverage with the `pytest-cov` plugin.

## Core Concepts Demonstrated

1.  **Pytest Fixtures**: Instead of `setUp/tearDown`, we use a `@pytest.fixture` to provide a clean, fresh `ShoppingCart` instance to each test that needs one. This is the modern, preferred way to handle test setup.
2.  **Pytest Assertions**: We use Python's simple, built-in `assert` statement. `pytest` provides detailed output on failures automatically.
3.  **Testing for Exceptions**: We use `pytest.raises` to verify that our code correctly raises errors under specific conditions (e.g., trying to add an item with a negative price).
4.  **Test Coverage**: We use the `pytest-cov` plugin to measure exactly which lines of our application code are executed by our tests. The goal is to identify untested parts of our application.

## Project Files

*   **`shopping_cart.py`**: The class we want to test. It contains logic for adding, removing, and calculating totals, including some error-checking.
*   **`test_shopping_cart_pytest.py`**: The test suite. It contains enough tests to exercise every line of code in `shopping_cart.py`, leading to 100% test coverage.

## How to Run This Example

### Step 1: Install Dependencies

You need `pytest` and `pytest-cov`. Install them using pip.

```bash
pip install pytest pytest-cov

pytest -v

pytest --cov=shopping_cart --cov-report term-missing

pytest --cov=shopping_cart --cov-report=html


-------------------------
**shopping_cart.py**
-------------------------
```python
# shopping_cart.py
# The application class we want to test.

class ShoppingCart:
    """A simple shopping cart class."""
    def __init__(self):
        # Items will be stored as { 'item_name': {'price': price, 'quantity': quantity} }
        self.items = {}

    def add_item(self, item_name, price, quantity=1):
        """Adds an item to the cart or updates its quantity."""
        # This is a branch we need to test
        if not isinstance(price, (int, float)) or price < 0:
            raise ValueError("Price must be a non-negative number.")

        # This is a branch we need to test (item already exists)
        if item_name in self.items:
            self.items[item_name]['quantity'] += quantity
        # This is another branch (new item)
        else:
            self.items[item_name] = {'price': price, 'quantity': quantity}

    def remove_item(self, item_name, quantity=1):
        """Removes a specified quantity of an item from the cart."""
        # This branch checks if the item is in the cart
        if item_name not in self.items:
            raise ValueError(f"{item_name} not in cart.")

        # This branch handles removing all or more items
        if self.items[item_name]['quantity'] <= quantity:
            del self.items[item_name]
        # This branch handles partial removal
        else:
            self.items[item_name]['quantity'] -= quantity

    def get_total(self):
        """Calculates the total price of all items in the cart."""
        total = 0
        for item in self.items.values():
            total += item['price'] * item['quantity']
        return total

# test_shopping_cart_pytest.py
# The test suite using pytest.

import pytest
from shopping_cart import ShoppingCart

# A pytest fixture to create a fresh cart instance for each test
@pytest.fixture
def cart():
    """Creates an empty ShoppingCart instance."""
    return ShoppingCart()

def test_initial_cart_is_empty(cart):
    """Test that a new cart is empty."""
    assert len(cart.items) == 0
    assert cart.get_total() == 0

def test_add_new_item(cart):
    """Test adding a completely new item."""
    cart.add_item("Apple", 0.5, 2)
    assert "Apple" in cart.items
    assert cart.items["Apple"]["price"] == 0.5
    assert cart.items["Apple"]["quantity"] == 2
    assert cart.get_total() == 1.0

def test_add_existing_item(cart):
    """Test adding more of an item that is already in the cart."""
    cart.add_item("Banana", 0.75, 1) # Add one banana
    cart.add_item("Banana", 0.75, 2) # Add two more bananas
    assert cart.items["Banana"]["quantity"] == 3
    assert cart.get_total() == 2.25

def test_remove_partial_quantity(cart):
    """Test removing some, but not all, of an item."""
    cart.add_item("Orange", 1.0, 5)
    cart.remove_item("Orange", 3)
    assert cart.items["Orange"]["quantity"] == 2
    assert cart.get_total() == 2.0

def test_remove_all_of_an_item(cart):
    """Test removing all of a specific item."""
    cart.add_item("Milk", 3.0, 1)
    cart.add_item("Bread", 2.5, 2)
    cart.remove_item("Milk", 1) # Remove the only milk
    assert "Milk" not in cart.items
    assert cart.get_total() == 5.0 # Bread total remains

# --- Tests for Error Conditions (Crucial for 100% Coverage) ---

def test_add_item_with_negative_price_raises_error(cart):
    """Test that adding an item with a negative price raises a ValueError."""
    # pytest.raises is a context manager that checks for expected exceptions.
    # The test passes only if a ValueError is raised inside the 'with' block.
    with pytest.raises(ValueError, match="Price must be a non-negative number."):
        cart.add_item("Bad Item", -1.0)

def test_remove_nonexistent_item_raises_error(cart):
    """Test that removing an item not in the cart raises a ValueError."""
    # We add an item just to make sure the cart isn't empty
    cart.add_item("Apple", 0.5)
    with pytest.raises(ValueError, match="Banana not in cart."):
        cart.remove_item("Banana") # "Banana" was never added
