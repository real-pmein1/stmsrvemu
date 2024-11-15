def list_user_subscriptions(info_type, user_info):
    parameters = [info_type, user_info]
    response = send_request_to_server('x08', parameters)

    if response:
        result = int(response[0])
        if result == 0:
            subscriptions = response[1:].split('\x00')
            for sub in subscriptions:
                print(sub)
        else:
            error_message = response[1:].strip('\x00')
            print(f"Error: {error_message}")
    else:
        print("Failed to get a response from the server.")

    show_post_action_menu()