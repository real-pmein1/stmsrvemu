import asyncio
from aiohttp import web
import os
import json


async def log_middleware(app, handler):
    """
    Middleware to log each request.
    """
    async def middleware_handler(request):
        client_ip = request.remote
        method = request.method
        url = str(request.url)
        print(f"Connection from {client_ip}: {method} {url}")
        return await handler(request)
    return middleware_handler


async def index(request):
    if os.path.exists('index.html'):
        return web.FileResponse('index.html')
    else:
        return web.Response(text="<html><body><h1>Welcome to My Async Server!</h1></body></html>", content_type='text/html')


async def static_handler(request):
    file_path = request.match_info.get('filename')
    static_file = os.path.join('static', file_path)
    if os.path.exists(static_file):
        return web.FileResponse(static_file)
    else:
        return web.Response(status=404, text="File Not Found")


async def hello(request):
    name = request.query.get('name', 'World')
    text = f"<html><body><h1>Hello, {name}!</h1></body></html>"
    return web.Response(text=text, content_type='text/html')


async def submit(request):
    if request.method == 'POST':
        post_data = await request.post()
        response_text = f"Data received via POST:\n{post_data}"
        return web.Response(text=response_text)
    else:
        return web.Response(status=405, text="Method Not Allowed")


async def hello_json(request):
    # Return a JSON response
    name = request.query.get('name', 'World')
    data = {'message': f'Hello, {name}!'}
    return web.json_response(data)


async def submit_json(request):
    # Accept JSON data in a POST request
    if request.method == 'POST':
        try:
            data = await request.json()
            # Process the JSON data as needed
            response_data = {'status': 'success', 'received_data': data}
            return web.json_response(response_data)
        except json.JSONDecodeError:
            return web.json_response({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    else:
        return web.json_response({'status': 'error', 'message': 'Method Not Allowed'}, status=405)


async def dynamic_js(request):
    code = "console.log('Dynamic JavaScript code executed');"
    return web.Response(text=code, content_type='application/javascript')


async def set_cookie(request):
    # Set a cookie via POST data
    if request.method == 'POST':
        data = await request.post()
        cookie_value = data.get('cookie_value', 'default_value')
        response = web.Response(text=f"Cookie set to: {cookie_value}")
        response.set_cookie('mycookie', cookie_value, max_age=3600)
        return response
    else:
        return web.Response(status=405, text="Method Not Allowed")


async def delete_cookie(request):
    # Delete the cookie
    response = web.Response(text="Cookie deleted")
    response.del_cookie('mycookie')
    return response


def create_app():
    app = web.Application(middlewares=[log_middleware])  # Add middleware here
    app.router.add_get('/', index)
    app.router.add_get('/hello', hello)
    app.router.add_get('/hello_json', hello_json)
    app.router.add_get('/static/{filename}', static_handler)
    app.router.add_route('*', '/submit', submit)
    app.router.add_post('/submit_json', submit_json)
    app.router.add_post('/set_cookie', set_cookie)
    app.router.add_get('/delete_cookie', delete_cookie)
    app.router.add_get('/dynamic.js', dynamic_js)
    return app


def main():
    app = create_app()
    port = 8080
    ssl_enabled = False  # Set to True if SSL is needed
    ssl_context = None

    if ssl_enabled:
        import ssl
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain('path/to/cert.pem', 'path/to/key.pem')

    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_exception)

    web.run_app(app, port=port, ssl_context=ssl_context)


def handle_exception(loop, context):
    exception = context.get("exception")
    if isinstance(exception, ConnectionResetError):
        pass
    else:
        loop.default_exception_handler(context)


if __name__ == '__main__':
    main()