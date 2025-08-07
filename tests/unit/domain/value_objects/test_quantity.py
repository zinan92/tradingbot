"""
Unit tests for Quantity value object

Tests business rules, validation, and operations for the Quantity value object.
Follows TDD principles with comprehensive test coverage.
"""

import pytest
from decimal import Decimal
from pydantic import ValidationError

from src.domain.trading.value_objects.quantity import Quantity


class TestQuantityCreation:
    """Test suite for Quantity creation and validation"""
    
    def test_create_quantity_from_int(self):
        """Test creating quantity from integer"""
        # Act
        quantity = Quantity(100)
        
        # Assert
        assert quantity.value == Decimal("100")
        assert isinstance(quantity.value, Decimal)
    
    def test_create_quantity_from_float(self):
        """Test creating quantity from float"""
        # Act
        quantity = Quantity(100.5)
        
        # Assert
        assert quantity.value == Decimal("100.5")
    
    def test_create_quantity_from_string(self):
        """Test creating quantity from string"""
        # Act
        quantity = Quantity("100.25")
        
        # Assert
        assert quantity.value == Decimal("100.25")
    
    def test_create_quantity_from_decimal(self):
        """Test creating quantity from Decimal"""
        # Arrange
        decimal_value = Decimal("100.75")
        
        # Act
        quantity = Quantity(decimal_value)
        
        # Assert
        assert quantity.value == Decimal("100.75")
    
    def test_quantity_is_immutable(self):
        """Test that quantity is immutable (frozen)"""
        # Arrange
        quantity = Quantity(100)
        
        # Act & Assert
        with pytest.raises(ValidationError):
            quantity.value = Decimal("200")
    
    def test_cannot_create_negative_quantity(self):
        """Test that negative quantities are rejected"""
        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            Quantity(-10)
        
        assert "must be positive" in str(exc.value).lower()
    
    def test_cannot_create_zero_quantity(self):
        """Test that zero quantity is rejected"""
        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            Quantity(0)
        
        assert "must be positive" in str(exc.value).lower()
    
    def test_cannot_create_quantity_from_invalid_type(self):
        """Test that invalid types are rejected"""
        # Act & Assert
        with pytest.raises(ValueError) as exc:
            Quantity([100])  # List is invalid
        
        assert "invalid quantity type" in str(exc.value).lower()
    
    def test_quantity_precision_rounding(self):
        """Test that quantities are rounded to 8 decimal places"""
        # Act
        quantity = Quantity("100.123456789")
        
        # Assert
        assert quantity.value == Decimal("100.12345679")  # Rounded to 8 places


class TestQuantityOperations:
    """Test suite for Quantity mathematical operations"""
    
    def test_add_quantities(self):
        """Test adding two quantities"""
        # Arrange
        qty1 = Quantity(100)
        qty2 = Quantity(50)
        
        # Act
        result = qty1.add(qty2)
        
        # Assert
        assert result.value == Decimal("150")
        assert isinstance(result, Quantity)
    
    def test_add_with_plus_operator(self):
        """Test adding quantities with + operator"""
        # Arrange
        qty1 = Quantity(100)
        qty2 = Quantity(50)
        
        # Act
        result = qty1 + qty2
        
        # Assert
        assert result.value == Decimal("150")
    
    def test_subtract_quantities(self):
        """Test subtracting quantities"""
        # Arrange
        qty1 = Quantity(100)
        qty2 = Quantity(30)
        
        # Act
        result = qty1.subtract(qty2)
        
        # Assert
        assert result.value == Decimal("70")
        assert isinstance(result, Quantity)
    
    def test_subtract_with_minus_operator(self):
        """Test subtracting quantities with - operator"""
        # Arrange
        qty1 = Quantity(100)
        qty2 = Quantity(30)
        
        # Act
        result = qty1 - qty2
        
        # Assert
        assert result.value == Decimal("70")
    
    def test_cannot_subtract_larger_quantity(self):
        """Test that subtracting larger quantity raises error"""
        # Arrange
        qty1 = Quantity(50)
        qty2 = Quantity(100)
        
        # Act & Assert
        with pytest.raises(Exception) as exc:
            qty1.subtract(qty2)
        
        assert "cannot subtract" in str(exc.value).lower()
    
    def test_multiply_quantity_by_factor(self):
        """Test multiplying quantity by a factor"""
        # Arrange
        quantity = Quantity(100)
        
        # Act
        result = quantity.multiply(2.5)
        
        # Assert
        assert result.value == Decimal("250")
        assert isinstance(result, Quantity)
    
    def test_multiply_with_asterisk_operator(self):
        """Test multiplying quantity with * operator"""
        # Arrange
        quantity = Quantity(100)
        
        # Act
        result = quantity * 3
        
        # Assert
        assert result.value == Decimal("300")
    
    def test_reverse_multiply(self):
        """Test reverse multiplication (factor * quantity)"""
        # Arrange
        quantity = Quantity(100)
        
        # Act
        result = 2 * quantity
        
        # Assert
        assert result.value == Decimal("200")
    
    def test_divide_quantity_by_number(self):
        """Test dividing quantity by a number"""
        # Arrange
        quantity = Quantity(100)
        
        # Act
        result = quantity.divide(4)
        
        # Assert
        assert result.value == Decimal("25")
        assert isinstance(result, Quantity)
    
    def test_divide_quantity_by_quantity_gives_ratio(self):
        """Test dividing quantity by another quantity gives ratio"""
        # Arrange
        qty1 = Quantity(100)
        qty2 = Quantity(25)
        
        # Act
        result = qty1.divide(qty2)
        
        # Assert
        assert result == Decimal("4")
        assert isinstance(result, Decimal)  # Not a Quantity
    
    def test_split_quantity_into_parts(self):
        """Test splitting quantity into equal parts"""
        # Arrange
        quantity = Quantity(100)
        
        # Act
        parts = quantity.split(4)
        
        # Assert
        assert len(parts) == 4
        assert all(isinstance(p, Quantity) for p in parts)
        assert all(p.value == Decimal("25") for p in parts)
        assert sum(p.value for p in parts) == quantity.value


class TestQuantityComparisons:
    """Test suite for Quantity comparison operations"""
    
    def test_quantity_equality(self):
        """Test quantity equality comparison"""
        # Arrange
        qty1 = Quantity(100)
        qty2 = Quantity(100)
        qty3 = Quantity(50)
        
        # Assert
        assert qty1 == qty2
        assert qty1 != qty3
        assert qty1.is_equal_to(qty2)
        assert not qty1.is_equal_to(qty3)
    
    def test_quantity_greater_than(self):
        """Test greater than comparison"""
        # Arrange
        qty1 = Quantity(100)
        qty2 = Quantity(50)
        
        # Assert
        assert qty1 > qty2
        assert qty1.is_greater_than(qty2)
        assert not qty2.is_greater_than(qty1)
    
    def test_quantity_greater_than_or_equal(self):
        """Test greater than or equal comparison"""
        # Arrange
        qty1 = Quantity(100)
        qty2 = Quantity(100)
        qty3 = Quantity(50)
        
        # Assert
        assert qty1 >= qty2
        assert qty1 >= qty3
        assert qty1.is_greater_than_or_equal(qty2)
        assert qty1.is_greater_than_or_equal(qty3)
    
    def test_quantity_less_than(self):
        """Test less than comparison"""
        # Arrange
        qty1 = Quantity(50)
        qty2 = Quantity(100)
        
        # Assert
        assert qty1 < qty2
        assert qty1.is_less_than(qty2)
        assert not qty2.is_less_than(qty1)
    
    def test_quantity_less_than_or_equal(self):
        """Test less than or equal comparison"""
        # Arrange
        qty1 = Quantity(50)
        qty2 = Quantity(50)
        qty3 = Quantity(100)
        
        # Assert
        assert qty1 <= qty2
        assert qty1 <= qty3
        assert qty1.is_less_than_or_equal(qty2)
        assert qty1.is_less_than_or_equal(qty3)
    
    def test_cannot_compare_quantity_with_non_quantity(self):
        """Test that comparing with non-Quantity raises error"""
        # Arrange
        quantity = Quantity(100)
        
        # Act & Assert
        with pytest.raises(TypeError):
            quantity.is_greater_than(100)  # Not a Quantity object


class TestQuantityConversions:
    """Test suite for Quantity type conversions"""
    
    def test_quantity_to_int(self):
        """Test converting quantity to integer"""
        # Arrange
        quantity = Quantity(100.75)
        
        # Act
        result = quantity.to_int()
        
        # Assert
        assert result == 100
        assert isinstance(result, int)
    
    def test_quantity_to_decimal(self):
        """Test getting raw decimal value"""
        # Arrange
        quantity = Quantity(100.25)
        
        # Act
        result = quantity.to_decimal()
        
        # Assert
        assert result == Decimal("100.25")
        assert isinstance(result, Decimal)
    
    def test_quantity_string_representation(self):
        """Test string representation of quantity"""
        # Arrange
        qty1 = Quantity(100)
        qty2 = Quantity(100.5)
        
        # Assert
        assert str(qty1) == "100"
        assert str(qty2) == "100.5"
    
    def test_quantity_repr(self):
        """Test developer representation of quantity"""
        # Arrange
        quantity = Quantity(100)
        
        # Assert
        assert repr(quantity) == "Quantity(value=100)"


class TestQuantityFactoryMethods:
    """Test suite for Quantity factory methods"""
    
    def test_from_lots(self):
        """Test creating quantity from lots"""
        # Act
        quantity = Quantity.from_lots(10, lot_size=100)
        
        # Assert
        assert quantity.value == Decimal("1000")
    
    def test_from_lots_with_default_lot_size(self):
        """Test creating quantity from lots with default size"""
        # Act
        quantity = Quantity.from_lots(5)
        
        # Assert
        assert quantity.value == Decimal("500")  # 5 * 100 (default)
    
    def test_minimum_quantity(self):
        """Test creating minimum valid quantity"""
        # Act
        quantity = Quantity.minimum()
        
        # Assert
        assert quantity.value == Decimal("0.00000001")
        assert quantity.value > 0


class TestQuantityHashingAndSets:
    """Test suite for Quantity hashing and set operations"""
    
    def test_quantity_is_hashable(self):
        """Test that quantities can be hashed"""
        # Arrange
        quantity = Quantity(100)
        
        # Act & Assert
        assert hash(quantity) is not None
    
    def test_quantities_in_set(self):
        """Test that quantities can be used in sets"""
        # Arrange
        qty1 = Quantity(100)
        qty2 = Quantity(100)  # Same value
        qty3 = Quantity(50)
        
        # Act
        quantity_set = {qty1, qty2, qty3}
        
        # Assert
        assert len(quantity_set) == 2  # qty1 and qty2 are equal
        assert qty1 in quantity_set
        assert qty3 in quantity_set
    
    def test_quantities_as_dict_keys(self):
        """Test that quantities can be used as dictionary keys"""
        # Arrange
        qty1 = Quantity(100)
        qty2 = Quantity(50)
        
        # Act
        quantity_dict = {
            qty1: "hundred",
            qty2: "fifty"
        }
        
        # Assert
        assert quantity_dict[qty1] == "hundred"
        assert quantity_dict[qty2] == "fifty"


class TestQuantityWithPrice:
    """Test suite for Quantity interactions with Price"""
    
    def test_calculate_value_with_price(self):
        """Test calculating monetary value from quantity and price"""
        # This would require Price value object to be available
        # Skipping for now as it tests integration
        pass


class TestQuantityEdgeCases:
    """Test suite for edge cases and boundary conditions"""
    
    def test_very_small_quantity(self):
        """Test handling very small quantities"""
        # Act
        quantity = Quantity("0.00000001")
        
        # Assert
        assert quantity.value == Decimal("0.00000001")
    
    def test_very_large_quantity(self):
        """Test handling very large quantities"""
        # Act
        quantity = Quantity("999999999999")
        
        # Assert
        assert quantity.value == Decimal("999999999999")
    
    def test_quantity_with_many_decimal_places(self):
        """Test quantity with many decimal places gets rounded"""
        # Act
        quantity = Quantity("100.999999999999")
        
        # Assert
        # Should be rounded to 8 decimal places
        assert len(str(quantity.value).split('.')[-1]) <= 8