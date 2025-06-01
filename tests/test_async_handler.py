import lark_oapi as lark

# 异步处理函数
async def async_message_handler() -> None:
    print("Async handler called")
    return

# 注册测试
event_handler = lark.EventDispatcherHandler.builder("", "") \
    .register_p2_im_message_receive_v1(async_message_handler) \
    .build()

print("Handler registered successfully")