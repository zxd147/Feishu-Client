async def async_return_test(a):
    if isinstance(a, str):
        result =  a * 3
    elif isinstance(a, list):
        result = ''.join([str(x) * 3 for x in a])
    elif hasattr(a, '__aiter__'):  # 显式检查异步迭代器
        result = ''
        async for item in a:
            result += str(item) * 3
    else:
        raise ValueError(f"Unsupported type: {type(a)}")
    return result


class MockAsyncIter:
    def __aiter__(self):
        self.data = ["a", "b", "c"]
        return self

    async def __anext__(self):
        if not self.data:
            raise StopAsyncIteration
        return self.data.pop(0)


async def main():
    # 测试字符串
    print(await async_return_test("a"))  # 输出: aaaaa...（100次）

    # 测试列表
    print(await async_return_test(["a", "b"]))  # 输出: b...b...（各100次）

    # 测试异步迭代器
    print(await async_return_test(MockAsyncIter()))  # 输出: aaa...bbb...ccc...（各100次）


if __name__ == '__main__':
    import asyncio

    asyncio.run(main())