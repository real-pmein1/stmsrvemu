anonUsersCount = 0

function_status = {
        'General':  {
                'RateLimitPerSec': 10, # packets per second
                'MaxSimulataniousUsers': 150, # maximum number of users that have packets processed at the same exact time
                'RequireEmailValidationForLogin':   False,
        },
        'CreateAccount': {
                'Enabled': True,
                'LimitPerHour': 2,
        },
        'Subscribe':    {
                'Enable': True,
                'LimitPerHour': 20,
        },
        'ChangeUserInfo':   {
                'Enabled':  True,
                'LimitPerHour': 2,
        },
        'Passes':   {
                'Enabled':  True,
                'SendLimitPerHour': 3,
                'ExpirationTimeInHours':    72,
        },
}