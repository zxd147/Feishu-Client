import asyncio
from concurrent.futures import ThreadPoolExecutor

# import nest_asyncio


# nest_asyncio.apply()


def sync1():
    print(111)
    # sync2()
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=1) as executor:
        loop.run_in_executor(executor, sync2)

def sync2():
    print(222)
    task()

# def sync2():
#     print(222)
#     thread = threading.Thread(target=sync2_thread)
#     thread.start()

# def sync2_thread():
#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)
#     loop.run_until_complete(loop.run_in_executor(None, task))


async def async1():
    print(111111)
    sync1()
    # loop = asyncio.get_event_loop()
    # with ThreadPoolExecutor() as executor:
    #     await loop.run_in_executor(executor, sync1)

async def async2():
    print(222222)
    print("end")

def task():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(async2())

async def main():
    print("start")
    await async1()
    await asyncio.sleep(0.2)

asyncio.run(main())