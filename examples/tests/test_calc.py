import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.calc import discount


def test_discount_normal():
    assert discount(100, 0) == 100
