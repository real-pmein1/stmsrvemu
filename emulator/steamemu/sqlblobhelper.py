'''user_registry = {
   Version '\x00\x00\x00\x00': '\x04\x00',
    Unique username '\x01\x00\x00\x00': 'hl2preload\x00',
    account creation time '\x02\x00\x00\x00': '\xe0\xe0\xe0\xe0\xe0\xe0\xe0\x00',
    OptionalAccountCreationKey  '\x03\x00\x00\x00': 'Egq-pe-y\x00',
  AccountUsersRecord   '\x06\x00\x00\x00':
    {
      username:  'hl2preload':
        {
         SteamLocalUserID   '\x01\x00\x00\x00': '\x80\x80\x80\x00\x00\x00\x00\x00',
           UserType  '\x02\x00\x00\x00': '\x01\x00', (odd numbers = admin, even = base)
          UserAppAccessRightsRecord   '\x03\x00\x00\x00':
            {
            }
        }
    },
   AccountUserPasswordsRecord '\x05\x00\x00\x00': {
       username 'hl2preload': {
           SaltedAnswerToQuestionDigest'\x04\x00\x00\x00':'4N\xf7\\\xcd\xec\xef\x88\x9aJ\xdak\x9cdb5;@\x19\x8a',
           PassphraseSalt '\x02\x00\x00\x00': '\xc5\xd9\x1d\x00\xc5&\xed\x8b',
           AnswerToQuestionSalt '\x05\x00\x00\x00': 'wc\x9b\xe7\xf5hmS',
          PersonalQuestion  '\x03\x00\x00\x00': 'Who was your childhood hero?\x00',
            SaltedPassphraseDigest'\x01\x00\x00\x00': '\xef8v\xd8\x94e\xf4\x0f\xb4\x1d\x9b\x94\x915QA\x16#*\x99'
        }
    },'''
  ''' AccountSubscriptionsRecord  '\x07\x00\x00\x00':
    {
      subscriptionid  '\x00\x00\x00\x00':
        {
         SubscribedDate   '\x01\x00\x00\x00': '\xe0\xe0\xe0\xe0\xe0\xe0\xe0\x00',
          UnsubscribedDate  '\x02\x00\x00\x00': '\x00\x00\x00\x00\x00\x00\x00\x00',
          SubscriptionStatus  '\x03\x00\x00\x00': '\x01\x00',
          StatusChangeFlag  '\x05\x00\x00\x00': '\x00',
          PreviousSubscriptionState  '\x06\x00\x00\x00': '\x1f\x00'
        }
    },
  DerivedSubscribedAppsRecord   '\x08\x00\x00\x00':
    {
    },
   LastRecalcDerivedSubscribedAppsTime  '\x09\x00\x00\x00': '\xe0\xe0\xe0\xe0\xe0\xe0\xe0\x00',
    Cellid '\x0a\x00\x00\x00': '\x05\x00\x00\x00',
    AccountEmailAddress  '\x0b\x00\x00\x00': 'hl2preload@poke.com\x00',
    
   AccountLastModifiedTime  '\x0e\x00\x00\x00': '\xe0\xe0\xe0\xe0\xe0\xe0\xe0\x00',
   AccountSubscriptionsBillingInfoRecord  '\x0f\x00\x00\x00':
    {
      SubscriptionBillingInfoTypeid   '\x00\x00\x00\x00':
        {
          AccountPaymentCardInfoRecord   '\x01\x00\x00\x00': '\x07',
          AccountPrepurchasedInfoRecord   '\x02\x00\x00\x00':
            {
            }
        },
     SubscriptionBillingInfoTypeid    '\x3d\x00\x00\x00':
        {
           AccountPaymentCardInfoRecord  '\x01\x00\x00\x00': '\x06',
          AccountPrepurchasedInfoRecord   '\x02\x00\x00\x00':
            {
               TypeOfProofOfPurchase '\x01\x00\x00\x00': 'ValveCDKey\x00',
                BinaryProofOfPurchaseToken '\x02\x00\x00\x00': '66666666\x00'
            },
        }
    }
}'''
'''
login order:
personalsalt = userblob['\x05\x00\x00\x00'][username]['\x02\x00\x00\x00']
key = userblob['\x05\x00\x00\x00'][username]['\x01\x00\x00\x00'][0:16]

from mysql_class import MySQLConnector

class AuthMysqlProcedures(MySQLConnector):
    def __init__(self):
        super(AuthMysqlProcedures, self).__init__()

    # Additional methods specific to the custom class

    def custom_method(self):
        # Custom functionality
        pass