### Логи ошибки, обработанные Sentry при вызове sentry-test

```text
Internal Server Error: /sentry-test/
Traceback (most recent call last):
  File "/home/elenadekho/diplom_project/venv/lib/python3.11/site-packages/django/core/handlers/exception.py", line 55, in inner
    response = get_response(request)
               ^^^^^^^^^^^^^^^^^^^^^
  File "/home/elenadekho/diplom_project/venv/lib/python3.11/site-packages/django/core/handlers/base.py", line 197, in _get_response
    response = wrapped_callback(request, *callback_args, **callback_kwargs)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/elenadekho/diplom_project/venv/lib/python3.11/site-packages/sentry_sdk/integrations/django/views.py", line 108, in sentry_wrapped_callback
    return callback(request, *args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/elenadekho/diplom_project/venv/lib/python3.11/site-packages/django/views/decorators/csrf.py", line 65, in _view_wrapper
    return view_func(request, *args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/elenadekho/diplom_project/venv/lib/python3.11/site-packages/django/views/generic/base.py", line 105, in view
    return self.dispatch(request, *args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/elenadekho/diplom_project/venv/lib/python3.11/site-packages/rest_framework/views.py", line 515, in dispatch
    response = self.handle_exception(exc)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/elenadekho/diplom_project/venv/lib/python3.11/site-packages/rest_framework/views.py", line 475, in handle_exception
    self.raise_uncaught_exception(exc)
  File "/home/elenadekho/diplom_project/venv/lib/python3.11/site-packages/rest_framework/views.py", line 486, in raise_uncaught_exception
    raise exc
  File "/home/elenadekho/diplom_project/venv/lib/python3.11/site-packages/rest_framework/views.py", line 512, in dispatch
    response = handler(request, *args, **kwargs)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/elenadekho/diplom_project/backend/views.py", line 1199, in get
    1 / 0
    ~~^~~
ZeroDivisionError: division by zero
[28/Jun/2026 20:01:47] "GET /sentry-test/ HTTP/1.1" 500 102282

