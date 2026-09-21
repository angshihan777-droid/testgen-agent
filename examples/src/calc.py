"""示例：折扣与区间判断模块（内置一个真实 bug 用于演示 bug 归因）。"""


def discount(price, level):
    """按会员等级返回折后价。level: 0 普通 / 1 银 / 2 金。"""
    if level == 1:
        rate = 0.9
    elif level == 2:
        rate = 0.8
    else:
        rate = 1.0
    return price * rate


def in_range(x, lo, hi):
    """判断 x 是否落在闭区间 [lo, hi] 内。"""
    # BUG: 上界用了 < 而非 <=，hi 这个点被漏判
    return lo <= x < hi
