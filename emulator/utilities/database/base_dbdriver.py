from datetime import datetime

from sqlalchemy import BLOB, BigInteger, Boolean, Column, DECIMAL, Date, DateTime, Float, ForeignKey, Integer, JSON, LargeBinary, SmallInteger, String, Text, Time, TypeDecorator, UniqueConstraint, event, text, update
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship


Base = declarative_base()


class custom_DateTime(TypeDecorator):
    """Stores datetimes in the database and converts back to datetime objects when retrieved."""
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(value, str):
            try:
                dt = datetime.strptime(value, '%m/%d/%Y %H:%M:%S')
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                raise ValueError("String is not in the correct datetime format 'mm/dd/yyyy hh:mm:ss'")
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            if isinstance(value, datetime):
                # The value is already a datetime object, return it as is
                return value
            # Parse the string assuming it's in 'yyyy-mm-dd hh:mm:ss' format to convert it back to a datetime object
            try:
                return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                raise ValueError("Database returned value is not in the expected datetime format 'YYYY-MM-DD HH:MM:SS'")
        return value


class ExecutedSQLFile(Base):
    __tablename__ = 'executed_sql_files'
    id = Column(Integer, primary_key = True)
    filename = Column(String(255), unique = True)


class GlobalIDSequence(Base):
    """
    Stores the sequence counter for GlobalID generation.
    Each box_id has its own sequence that increments for each new GlobalID.
    The sequence resets when the start_time changes (typically per-second).
    """
    __tablename__ = 'globalid_sequence'
    box_id = Column(Integer, primary_key=True)
    last_start_time = Column(Integer, nullable=False, default=0)  # Seconds since 2005-01-01
    sequence_count = Column(Integer, nullable=False, default=0)  # Current sequence within the start_time


# 2002 Beta 1 Tables
class Beta1_User(Base):
    __tablename__ = 'beta1_users'
    id = Column(Integer, primary_key = True, autoincrement = True)  # Auto-incrementing primary key
    username = Column(String(128), unique = True)  # Ensuring username uniqueness
    createtime = Column(Integer)
    accountkey = Column(String(100))
    salt = Column(String(100))
    hash = Column(String(100))

class Beta1_Subscriptions(Base):
    __tablename__ = 'beta1_subscriptions'
    username = Column(String(128), primary_key = True)
    subid = Column(Integer, primary_key = True)
    subtime = Column(Integer)

class Beta1_TrackerRegistry(Base):
    __tablename__ = 'beta1_tracker_registry'
    uniqueid = Column(Integer, primary_key = True, autoincrement = True)  # Auto-incrementing primary key
    username = Column(String(128), unique = True)  # Ensuring username uniqueness
    firstname = Column(String(100))
    lastname = Column(String(100))
    email = Column(String(100))
    password = Column(String(100))

class Beta1_Friendslist(Base):
    __tablename__ = 'beta1_tracker_friendslist'
    uniqueid = Column(Integer, primary_key = True, autoincrement = True)
    source = Column(Integer, ForeignKey('beta1_tracker_registry.uniqueid'))
    target = Column(Integer, ForeignKey('beta1_tracker_registry.uniqueid'))


# Log related table
# TODO Eventually Log ALL user activities in the database for posterity!
class UserActivities(Base):
    __tablename__ = 'useractivities'
    LogID = Column(Integer, primary_key = True, autoincrement = True)
    SteamID = Column(String(64), nullable = False)
    UserName = Column(String(100))
    UserIP = Column(String(128))
    LogDate = Column(Date)
    LogTime = Column(Time)
    Activity = Column(String(255))
    Notes = Column(Text)

class UserRegistry(Base):
    __tablename__ = 'userregistry'
    UniqueID = Column(Integer, primary_key=True, autoincrement=True) # This is the SteamID
    UniqueUserName = Column(String(256), nullable=False, unique = True)
    AccountCreationTime = Column(String(355), nullable=False)
    UserType = Column(Integer, nullable=False, default=1)
    SaltedAnswerToQuestionDigest = Column(String(512), nullable=False)
    PassphraseSalt = Column(String(512), nullable=False)
    AnswerToQuestionSalt = Column(String(512), nullable=False)
    PersonalQuestion = Column(String(256), nullable=False)
    SaltedPassphraseDigest = Column(String(512), nullable=False)
    LastRecalcDerivedSubscribedAppsTime = Column(String(45), nullable=False)
    CellID = Column(Integer, default=1)
    AccountEmailAddress = Column(String(256), nullable=False)
    Banned = Column(Integer, nullable=False, default=0)
    AccountLastModifiedTime = Column(String(45), nullable=False, default='e0 e0 e0 e0 e0 e0 e0 00')
    DerivedSubscribedAppsRecord = Column(Text(256))
    email_verified = Column(Integer, nullable=False, default=0)
    email_verificationcode = Column(String(46))
    info_change_validation_time = Column(String(46))
    info_change_validation_code = Column(String(25))
    ipaddress = Column(String(128))
    loginkey = Column(String(128))
    sessionkey = Column(String(128))
    symmetric_key = Column(String(256))
    ufsSessionToken = Column(String(16))
    # community = relationship("friends_registry", backref = "user", uselist = False)

class AccountExternalBillingInfoRecord(Base):
    __tablename__ = 'accountexternalbillinginforecord'
    UniqueID = Column(Integer, primary_key=True, autoincrement=True)
    ExternalAccountName = Column(String(256))
    ExternalAccountPassword = Column(String(256))

class AccountPaymentCardInfoRecord(Base):
    __tablename__ = 'accountpaymentcardinforecord'
    UniqueID = Column(Integer, primary_key=True, autoincrement=True)
    UserRegistry_UniqueID = Column(Integer, ForeignKey('userregistry.UniqueID'))
    PaymentCardType = Column(Integer)
    CardNumber = Column(String(255))
    CardHolderName = Column(String(255))
    CardExpYear = Column(String(8))
    CardExpMonth = Column(String(8))
    CardCVV2 = Column(String(8))
    BillingAddress1 = Column(String(255))
    BillingAddress2 = Column(String(255))
    BillingCity = Column(String(255))
    BillingZip = Column(String(25))
    BillingState = Column(String(100))
    BillingCountry = Column(String(255))
    BillingPhone = Column(String(20))
    BillinEmailAddress = Column(String(255))
    CCApprovalDate = Column(Date)
    CCApprovalCode = Column(Integer)
    CDenialDate = Column(Date)
    CDenialCode = Column(String(255))
    UseAVS = Column(Integer)
    PriceBeforeTax = Column(DECIMAL(50, 2))
    TaxAmount = Column(DECIMAL(50, 2))
    TransactionType = Column(String(4))
    AuthComments = Column(String(255))
    AuthStatus = Column(String(6))
    AuthSource = Column(String(25))
    AuthResponse = Column(String(25))
    TransDate = Column(String(255))
    TransTime = Column(String(255))
    PS2000Data = Column(Text)
    SettlementDate = Column(Date)
    SettlementCode = Column(Integer)
    CCTSResponseCode = Column(String(25))
    SettlementBatchId = Column(Integer)
    SettlementBatchSeq = Column(Integer)
    SettlementApprovalCode = Column(Integer)
    SettlementComments = Column(String(255))
    SettlementStatus = Column(String(1))
    AStoBBSTxnId = Column(Integer)
    SubsId = Column(Integer)
    AcctName = Column(String(255))
    CC1TimeChargeTxnSeq = Column(Integer)
    CustSupportName = Column(String(255))
    ChargeBackCaseNumber = Column(String(255))
    GetCreditForceTxnSeq = Column(Integer)
    ShippingInfoRecord = Column(Integer)
    CVV2Response = Column(String(255))


class AccountPrepurchasedInfoRecord(Base):
    __tablename__ = 'accountprepurchasedinforecord'
    UniqueID = Column(Integer, primary_key=True, autoincrement=True)
    UserRegistry_UniqueID = Column(Integer, ForeignKey('userregistry.UniqueID'))
    TypeOfProofOfPurchase = Column(String(45))
    BinaryProofOfPurchaseToken = Column(String(255))
    TokenRejectionReason = Column(String(255))
    SubsId = Column(Integer)
    CustSupportName = Column(String(150))

class AccountSubscriptionsBillingInfoRecord(Base):
    __tablename__ = 'accountsubscriptionsbillinginforecord'
    UniqueID = Column(Integer, primary_key=True, autoincrement=True)
    UserRegistry_UniqueID = Column(Integer, ForeignKey('userregistry.UniqueID'))
    SubscriptionID = Column(Integer)
    AccountPaymentType = Column(Integer)
    AccountPrepurchasedInfoRecord_UniqueID = Column(Integer, ForeignKey('accountprepurchasedinforecord.UniqueID'))
    AccountExternalBillingInfoRecord_UniqueID = Column(Integer, ForeignKey('accountexternalbillinginforecord.UniqueID'))
    AccountPaymentCardReceiptRecord_UniqueID = Column(Integer, ForeignKey('accountpaymentcardinforecord.UniqueID'))

class AccountSubscriptionsRecord(Base):
    __tablename__ = 'accountsubscriptionsrecord'
    UniqueID = Column(Integer, primary_key=True, autoincrement=True)
    UserRegistry_UniqueID = Column(Integer, ForeignKey('userregistry.UniqueID'))
    SubscriptionID = Column(Integer)
    SubscribedDate = Column(String(45), default='01/12/2024 17:25:34')
    UnsubscribedDate = Column(String(45), default='01/12/2024 17:25:34')
    SubscriptionStatus = Column(Integer, default=1)
    StatusChangeFlag = Column(Integer, default=0)
    PreviousSubscriptionState = Column(Integer, default=31)
    OptionalBillingStatus = Column(String(12))
    UserIP = Column(String(128))
    UserCountryCode = Column(String(16))

class SteamApplications(Base):
    __tablename__ = 'steamapplications'
    AppID = Column(Integer, primary_key=True, unique = True)
    Name = Column(String(256))

class SteamSubApps(Base):
    __tablename__ = 'steamsub_apps'
    UniqueID = Column(Integer, primary_key=True, autoincrement=True)
    SteamSubscriptions_SubscriptionID = Column(Integer, nullable=False)
    AppList = Column(String(1000))

class SteamSubscriptions(Base):
    __tablename__ = 'steamsubscriptions'
    SubscriptionID = Column(Integer, primary_key=True, unique = True)
    Name = Column(String(256))

# FIXME was this for enabling or disabling subscriptions?
#class SubscriptionStatus(Base):
#    __tablename__ = 'subscriptionstatus'
#    uniqueid = Column(Integer, primary_key=True, autoincrement=True)
#    statustype = Column(String(100), nullable=False)

class UserAppAccessRightsRecord(Base):
    __tablename__ = 'userappaccessrightsrecord'
    UniqueID = Column(Integer, primary_key=True, autoincrement=True)
    UserRegistry_UniqueID = Column(Integer, ForeignKey('userregistry.UniqueID'), nullable=False)
    AppID = Column(Integer, nullable=False)
    Rights = Column(String(128))

# FIXME eventually use this for the admin server and for general user permissions
#class UserPermissions(Base):
#    __tablename__ = 'userpermissions'
#    UniqueID = Column(Integer, primary_key=True, autoincrement=True)
#    UserRegistry_UniqueID = Column(Integer, ForeignKey('userregistry.UniqueID'), nullable=False)
#    Rights = Column(Integer, nullable=False)
    #ccpayments, cdkey subscription, change email, change password, change question, login to friends

class AuthenticationTicketsRecord(Base):
    __tablename__ = 'authenticationticketsrecord'
    #  uniqueID = Column(Integer)
    UserRegistry_UniqueID = Column(Integer, ForeignKey('userregistry.UniqueID'), primary_key = True)
    UserIPAddress = Column(String(60))
    TicketCreationTime = Column(custom_DateTime())
    TicketExpirationTime = Column(custom_DateTime())
    TicketData = Column(LargeBinary)


class AuthenticationTicketLog(Base):
    __tablename__ = 'authenticationticketlog'
    id = Column(Integer, primary_key=True, autoincrement=True)
    UserRegistry_UniqueID = Column(Integer, ForeignKey('userregistry.UniqueID'))
    TicketData = Column(LargeBinary)
    TicketCreationTime = Column(custom_DateTime())
    TicketExpirationTime = Column(custom_DateTime())


class FriendsRegistry(Base):
    __tablename__ = 'friends_registry'
    UniqueID = Column(Integer,  autoincrement = True)
    accountID = Column(Integer, ForeignKey('userregistry.UniqueID'), primary_key = True)
    nickname = Column(String(100))
    status = Column(Integer)
    primary_clanID = Column(Integer, ForeignKey('Community_ClanRegistry.UniqueID'), nullable = True)
    primary_groupID = Column(Integer, ForeignKey('Friends_groups.UniqueID'), nullable = True)
    currently_playing = Column(Integer, ForeignKey('friends_play_history.UniqueID'), nullable = True)
    last_login = Column(custom_DateTime())
    last_logoff = Column(custom_DateTime())

    play_history = relationship(
        "FriendsPlayHistory",
        backref="user",
        foreign_keys=[currently_playing]  # Specify the foreign key explicitly
    )
    groups_owned = relationship(
            "FriendsGroups",
            backref = "owner",
            foreign_keys = "[FriendsGroups.owner_accountID]",
            uselist = True
    )
    chatrooms_owned = relationship(
            "ChatRoomRegistry",
            backref = "owner",
            foreign_keys = "[ChatRoomRegistry.owner_accountID]",
            uselist = True
    )
    community_profile = relationship(
            "CommunityRegistry",
            backref = "user",
            foreign_keys = "[CommunityRegistry.friendRegistryID]",
            uselist = False
    )
    name_history = relationship(
            "FriendsNameHistory",
            backref = "user",
            foreign_keys = "[FriendsNameHistory.friendRegistryID]",
            uselist = True
    )
    offline_messages = relationship(
            "FriendsOfflineMsgs",
            foreign_keys = "[FriendsOfflineMsgs.to_AccountID]",
            backref = "recipient"
    )
    friends = relationship(
            "FriendsList",
            foreign_keys = "[FriendsList.friendRegistryID]",
            primaryjoin = "FriendsRegistry.UniqueID==FriendsList.friendRegistryID",
            cascade = "all, delete-orphan",
            uselist = True
    )
    clans = relationship(
            "CommunityClanRegistry",
            backref = "owner",
            foreign_keys = "[CommunityClanRegistry.owner_accountID]",
            uselist = True
    )
    lobbies = relationship(
            "LobbyRegistry",
            backref = "owner",
            foreign_keys = "[LobbyRegistry.owner_accountID]",
            uselist = True
    )
    inventory_items = relationship(
            "ClientInventoryItems",
            backref = "owner",
            foreign_keys = "[ClientInventoryItems.friendRegistryID]",
            uselist = True
    )
    leaderboard_entries = relationship(
            "LeaderboardEntry",
            backref = "participant",
            foreign_keys = "[LeaderboardEntry.friendRegistryID]",
            uselist = True
    )
    rich_presence_entries = relationship(
            "RichPresence",
            backref = "user",
            foreign_keys = "[RichPresence.friendRegistryID]",
            uselist = True
    )
    vac_bans = relationship(
            "VACBans",
            backref = "user",
            foreign_keys = "[VACBans.friendRegistryID]",
            uselist = True
    )
    #games_played = relationship("FriendsGamesPlayedHistory", backref="player", uselist = True)

class VACBans(Base):
    __tablename__ = 'VACBans'
    UniqueID = Column(Integer, primary_key = True, autoincrement=True)
    friendRegistryID  = Column(Integer, ForeignKey('friends_registry.accountID'))
    starttime = Column(custom_DateTime(), nullable=False)
    length_of_ban = Column(Integer) # in hours
    firstappid = Column(Integer)
    lastappid = Column(Integer)


class FriendsPlayHistory(Base):
    __tablename__ = 'friends_play_history'
    UniqueID = Column(Integer, primary_key = True)
    friendRegistryID  = Column(Integer, ForeignKey('friends_registry.accountID'))
    processID = Column(Integer)
    appID = Column(Integer)
    name = Column(String(256))
    serverID = Column(Integer)
    server_ip = Column(BigInteger)
    server_port = Column(Integer)
    game_data = Column(BLOB)
    token_crc = Column(Integer)
    vr_hmd_vendor = Column(String(256))
    vr_hmd_model = Column(String(256))
    launch_option_type = Column(Integer)
    vr_hmd_runtime = Column(Integer)
    controller_connection_type = Column(Integer)
    start_datetime = Column(DateTime)
    end_datetime = Column(DateTime)


class FriendsList(Base):
    __tablename__ = 'friends_friendslist'
    UniqueID = Column(Integer, primary_key=True, autoincrement=True)
    friendRegistryID = Column(Integer, ForeignKey('friends_registry.accountID'))
    friendsaccountID = Column(Integer, ForeignKey('friends_registry.accountID'))
    relationship = Column(Integer, default=0)
    friend_date = Column(custom_DateTime())
    notification_showingame = Column(SmallInteger)
    notification_showonline = Column(SmallInteger)
    notification_sendmobile = Column(SmallInteger)
    notification_showmessages = Column(SmallInteger)
    sounds_showingame = Column(SmallInteger)
    sounds_showonline = Column(SmallInteger)
    sounds_showmessages = Column(SmallInteger)
    __table_args__ = (UniqueConstraint('friendRegistryID', 'friendsaccountID'),)

    @staticmethod
    def after_insert(mapper, connection, target):
        if target.friendRegistryID and target.friendsaccountID:
            inverse_relationship = 3 if target.relationship == 3 else 2
            connection.execute(
                    FriendsList.__table__.insert(),
                    {
                            "friendRegistryID":         target.friendsaccountID,
                            "friendsaccountID":         target.friendRegistryID,
                            "relationship":             inverse_relationship,
                            "notification_showingame":  target.notification_showingame,
                            "notification_showonline":  target.notification_showonline,
                            "notification_sendmobile":  target.notification_sendmobile,
                            "notification_showmessages":target.notification_showmessages,
                            "sounds_showingame":        target.sounds_showingame,
                            "sounds_showonline":        target.sounds_showonline,
                            "sounds_showmessages":      target.sounds_showmessages
                    }
            )

    @staticmethod
    def after_delete(mapper, connection, target):
        if target.friendRegistryID and target.friendsaccountID:
            # Delete the reciprocal entry
            connection.execute(
                    FriendsList.__table__.delete().where(
                            (FriendsList.friendRegistryID == target.friendsaccountID) &
                            (FriendsList.friendsaccountID == target.friendRegistryID)
                    )
            )

    @staticmethod
    def after_update(mapper, connection, target):
        if target.friendRegistryID and target.friendsaccountID:
            current_datetime = datetime.now()
            if target.relationship == 3:
                previous_relationship = connection.execute(
                    FriendsList.__table__.select()
                    .with_only_columns(FriendsList.relationship)
                    .where(
                        (FriendsList.friendRegistryID == target.friendRegistryID) &
                        (FriendsList.friendsaccountID == target.friendsaccountID)
                    )
                ).fetchone().relationship

                if previous_relationship == 5:
                    # Update inverse entry if the relationship was 6
                    inverse_entry = connection.execute(
                        FriendsList.__table__.select().where(
                            (FriendsList.friendRegistryID == target.friendsaccountID) &
                            (FriendsList.friendsaccountID == target.friendRegistryID) &
                            (FriendsList.relationship == 6)
                        )
                    ).fetchone()

                    if inverse_entry:
                        connection.execute(
                            update(FriendsList.__table__)
                            .where(
                                (FriendsList.friendRegistryID == target.friendsaccountID) &
                                (FriendsList.friendsaccountID == target.friendRegistryID)
                            )
                            .values(relationship=3)
                        )

                else:
                    # Update inverse entry if the relationship is 2 or 4
                    inverse_entry = connection.execute(
                        FriendsList.__table__.select().where(
                            (FriendsList.friendRegistryID == target.friendsaccountID) &
                            (FriendsList.friendsaccountID == target.friendRegistryID) &
                            (FriendsList.relationship.in_([2, 4]))
                        )
                    ).fetchone()

                    if inverse_entry:
                        connection.execute(
                            update(FriendsList.__table__)
                            .where(
                                (FriendsList.friendRegistryID == target.friendsaccountID) &
                                (FriendsList.friendsaccountID == target.friendRegistryID)
                            )
                            .values(relationship=3, friend_date=current_datetime)
                        )

                    # Update the target entry's friend_date
                    connection.execute(
                        update(FriendsList.__table__)
                        .where(
                            (FriendsList.friendRegistryID == target.friendRegistryID) &
                            (FriendsList.friendsaccountID == target.friendsaccountID)
                        )
                        .values(friend_date=current_datetime)
                    )
            elif target.relationship == 5:
                inverse_entry = connection.execute(
                    FriendsList.__table__.select().where(
                        (FriendsList.friendRegistryID == target.friendsaccountID) &
                        (FriendsList.friendsaccountID == target.friendRegistryID)
                    )
                ).fetchone()

                if inverse_entry:
                    connection.execute(
                        update(FriendsList.__table__)
                        .where(
                            (FriendsList.friendRegistryID == target.friendsaccountID) &
                            (FriendsList.friendsaccountID == target.friendRegistryID)
                        )
                        .values(relationship=6)
                    )


# Adding the event listeners
event.listen(FriendsList, 'after_insert', FriendsList.after_insert)
event.listen(FriendsList, 'after_delete', FriendsList.after_delete)
event.listen(FriendsList, 'after_update', FriendsList.after_update)


class FriendsGroups(Base):
    __tablename__ = 'Friends_groups'
    UniqueID = Column(Integer, primary_key = True, autoincrement = True) # group id
    owner_accountID = Column(Integer, ForeignKey('friends_registry.accountID'))
    name = Column(String(256), unique = True)
    abbreviated_name = Column(String(256), unique = True)
    url = Column(String(256), unique = True)
    avatar = Column(String(256))
    description = Column(String(1024))
    is_public = Column(SmallInteger)
    # Make associated_chatid a ForeignKey to ChatRoomRegistry.UniqueID
    associated_chatid = Column(Integer, ForeignKey('chatrooms_registry.UniqueID'), nullable = True)
    # Add a relationship to the associated ChatRoomRegistry
    associated_chatroom = relationship("ChatRoomRegistry", backref = "associated_group", foreign_keys = [associated_chatid])
    creationdate = Column(custom_DateTime())
    player_otw = Column(Integer)
    owner_permissions = Column(Integer, default = 0)
    moderator_permissions = Column(Integer, default = 0)
    member_permissions = Column(Integer, default = 0)
    default_permissions = Column(Integer, default = 0)
    headLine = Column(String(255), default = '')
    summary = Column(String(512), default = '')
    country = Column(String(128), default = '')
    state = Column(String(128), default = '')
    city = Column(String(200), default = '')
    website_title1 = Column(String(255), default = '')
    website_url1 = Column(String(255), default = '')
    website_title2 = Column(String(255), default = '')
    website_url2 = Column(String(255), default = '')
    website_title3 = Column(String(255), default = '')
    website_url3 = Column(String(255), default = '')
    members = relationship("FriendsGroupMembers", backref = "group")

class FriendsGroupMembers(Base):
    __tablename__ = 'Friends_Group_Members'
    UniqueID = Column(Integer, primary_key = True, autoincrement=True)
    GroupID = Column(Integer, ForeignKey('Friends_groups.UniqueID'), )
    friendRegistryID = Column(Integer, ForeignKey('friends_registry.accountID'))
    #nickname = Column(String(256))
    relation = Column(Integer)

class FriendsOfflineMsgs(Base):
    __tablename__ = 'Friends_Offline_Msgs'
    UniqueID = Column(Integer, primary_key = True, autoincrement=True)
    from_accountID = Column(Integer, ForeignKey('friends_registry.accountID'))
    to_AccountID = Column(Integer, ForeignKey('friends_registry.accountID'))
    message = Column(String(255), default = '')
    datetime = Column(custom_DateTime())

class FriendsChatHistory(Base):
    __tablename__ = 'Friends_Chat_History'
    UniqueID = Column(Integer, primary_key = True, autoincrement=True)
    from_accountID = Column(Integer, ForeignKey('friends_registry.accountID'))
    to_accountID = Column(Integer, ForeignKey('friends_registry.accountID'))
    datetime = Column(custom_DateTime())
    message = Column(String(255), default = '')
    acked = Column(Integer, default = 0)

class FriendsNameHistory(Base):
    __tablename__ = 'Friends_Nickname_History'
    UniqueID = Column(Integer, primary_key = True, autoincrement=True)
    friendRegistryID = Column(Integer, ForeignKey('friends_registry.accountID'))
    nickname = Column(String(255), default = '')
    datetime = Column(custom_DateTime)

#class FriendsGamesPlayedHistory(Base):
#    __tablename__ = 'Friends_Games_Played_History'
#    UniqueID = Column(Integer, primary_key = True, autoincrement=True)
#    accountID = Column(Integer, ForeignKey('friends_registry.accountID'))
#    appid = Column(Integer, default = 0)
#    hours_played = Column(Integer, default = 0)
#    last_play_datetime = Column(String(255), default = '')

class CommunityRegistry(Base):
    __tablename__ = 'Community_Profile'
    UniqueID = Column(Integer, primary_key = True, autoincrement=True)
    friendRegistryID = Column(Integer, ForeignKey('friends_registry.accountID'), unique = True)
    real_name = Column(String(255), default = '')
    headLine = Column(String(255), default = '')
    summary = Column(String(512), default = '')
    profile_url = Column(String(255), unique = True)
    country = Column(String(128), default = '')
    state = Column(String(128), default = '')
    city = Column(String(200), default = '')
    website_title1 = Column(String(255), default = '')
    website_url1 = Column(String(255), default = '')
    website_title2 = Column(String(255), default = '')
    website_url2 = Column(String(255), default = '')
    website_title3 = Column(String(255), default = '')
    website_url3 = Column(String(255), default = '')
    avatarID = Column(String(255), default = '')
    profile_visibility = Column(Integer, default = 0) # 0 = public, 1 = friends only, 3 = private
    comment_permissions = Column(Integer, default = 1) # 0 = anyone can comment, 1 = friends only, 2 = private/no one can comment
    onetime_pass = Column(String(17), default = '')
    welcome = Column(Boolean, default = False)
    facebook_name = Column(String(200), default = '')
    facebookID = Column(Integer, default = 0)

##################################
#            ChatRooms           #
##################################
class ChatRoomRegistry(Base):
    __tablename__ = 'chatrooms_registry'
    UniqueID = Column(Integer, primary_key = True, autoincrement=True)
    chatroom_type = Column(Integer, default = 0)
    owner_accountID = Column(Integer, ForeignKey('friends_registry.accountID'), default = 1)
    groupID = Column(Integer, ForeignKey('Friends_groups.UniqueID'), nullable = True)
    appID = Column(Integer, default = 0)
    chatroom_name = Column(String(255), default = '')
    datetime = Column(custom_DateTime())
    message = Column(String(255), default = '') # FIXME rename to MOTD?
    servermessage = Column(Integer, default = 0)
    chatroom_flags = Column(Integer, default = 0)
    owner_permissions = Column(Integer, default = 0)
    moderator_permissions = Column(Integer, default = 0)
    member_permissions = Column(Integer, default = 0)
    default_permissions = Column(Integer, default = 0)
    maxmembers = Column(Integer, default = 0)
    locked = Column(Integer, default = 0)
    metadata_info = Column(String(255), default = '')
    current_usercount = Column(Integer, default = 0)
    members = relationship("ChatRoomMembers", backref="chat_room")
    speakers = relationship("ChatRoomSpeakers", backref="chat_room")
    __table_args__ = (UniqueConstraint('chatroom_name', 'appID'),)

class ChatRoomMembers(Base):
    __tablename__ = 'chatroom_members'
    UniqueID = Column(Integer, primary_key = True, autoincrement = True)
    chatRoomID = Column(Integer, ForeignKey('chatrooms_registry.UniqueID'))
    friendRegistryID = Column(Integer, ForeignKey('friends_registry.accountID'))
    relationship = Column(Integer)
    inviterAccountID = Column(Integer, ForeignKey('friends_registry.accountID'), nullable = True)
    memberRankDetails = Column(Integer, default = 0)
    __table_args__ = (UniqueConstraint('chatRoomID', 'friendRegistryID'),)

class ChatRoomSpeakers(Base):
    __tablename__ = 'chatroom_speakers'
    UniqueID = Column(Integer, primary_key = True, autoincrement = True)
    chatRoomID = Column(Integer, ForeignKey('chatrooms_registry.UniqueID'))
    friendRegistryID = Column(Integer, ForeignKey('friends_registry.accountID'))
    __table_args__ = (UniqueConstraint('chatRoomID', 'friendRegistryID'),)

class ChatRoomHistory(Base):
    __tablename__ = 'ChatRoom_History'
    UniqueID = Column(Integer, primary_key = True, autoincrement=True)
    chatroomID = Column(Integer, ForeignKey('chatrooms_registry.UniqueID'))
    from_accountID = Column(Integer, ForeignKey('friends_registry.accountID'))
    datetime = Column(custom_DateTime())
    message = Column(String(255), default = '')
    servermessage = Column(Integer, default = 0)
    account_parameters = Column(Integer, default = 0)
    string_parameters = Column(Integer, default = 0)
    isdeleted = Column(Integer, default = 0)

##################################
#              Clan              #
##################################

class CommunityClanRegistry(Base):
    __tablename__ = 'Community_ClanRegistry'
    UniqueID = Column(Integer, primary_key = True, autoincrement=True)
    clan_name= Column(String(255), unique = True)
    clan_tag = Column(String(10), unique = True)
    owner_accountID = Column(Integer, ForeignKey('friends_registry.accountID'))
    clan_status = Column(Integer)
    profile_permisions = Column(Integer)
    moderator_permissions = Column(Integer)
    event_permissions = Column(Integer)
    potw_permissions = Column(Integer)
    invite_permissions = Column(Integer)
    kick_permissions = Column(Integer)
    # Relationships
    members = relationship("CommunityClanMembers", backref = "clan", cascade = "all, delete-orphan")
    events = relationship("CommunityClanEvents", backref = "clan", cascade = "all, delete-orphan")

class CommunityClanMembers(Base):
    __tablename__ = 'Community_Clan_Members'
    UniqueID = Column(Integer, primary_key = True, autoincrement = True)
    CommunityClanID = Column(Integer, ForeignKey('Community_ClanRegistry.UniqueID'))
    friendRegistryID = Column(Integer, ForeignKey('friends_registry.accountID'))
    user_rank = Column(Integer)
    relationship = Column(Integer)
    is_maingroup = Column(Boolean)
    __table_args__ = (UniqueConstraint('CommunityClanID', 'friendRegistryID'),)

class CommunityClanEvents(Base):
    __tablename__ = 'community_clan_events'
    eventID = Column(Integer, primary_key = True, autoincrement = True)
    CommunityClanID = Column(Integer, ForeignKey('Community_ClanRegistry.UniqueID'))  # Assuming there's a Clan Registry table
    start_time = Column(Integer)  # Consider using DateTime type if dealing with actual date/time values
    event_name = Column(String(256))
    event_type = Column(Integer)
    appID = Column(Integer)
    game_server = Column(String(256))
    game_server_pass = Column(String(256))
    description = Column(String(1024))
    timestamp = Column(custom_DateTime())
    announcement = Column(Integer)

##################################
#           Inventory            #
##################################

class ClientInventoryItems(Base):
    __tablename__ = 'Client_Inventory_Items'
    UniqueID = Column(Integer, primary_key = True, autoincrement = True)
    friendRegistryID = Column(Integer, ForeignKey('friends_registry.accountID'))
    itemID = Column(Integer, unique = True)
    appID = Column(Integer)
    quantity = Column(Integer)
    acquired = Column(Integer)
    price = Column(String(25))
    state = Column(String(100))
    transactionID = Column(Integer)
    origin = Column(String(100))
    original_itemID = Column(Integer)
    position = Column(Integer)
    trade_after_datetime = Column(String(100))


class PersistentItem(Base):
    __tablename__ = 'persistent_items'

    id = Column(Integer, primary_key=True, autoincrement=True)
    steam_id = Column(BigInteger, nullable=False)
    app_id = Column(Integer, nullable=False)
    item_id = Column(BigInteger, nullable=False, unique=True)
    definition_index = Column(Integer, nullable=False)
    item_level = Column(Integer, nullable=False)
    quality = Column(Integer, nullable=False)
    inventory_token = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=False)
    blob_data = Column(LargeBinary(1024), nullable=True)  # Up to 1024 bytes of custom item data

    attributes = relationship("PersistentItemAttribute", back_populates="item", cascade="all, delete-orphan")


class PersistentItemAttribute(Base):
    __tablename__ = 'persistent_item_attributes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(Integer, ForeignKey('persistent_items.id'), nullable=False)
    definition_index = Column(Integer, nullable=False)
    value = Column(Float, nullable=False)

    item = relationship("PersistentItem", back_populates="attributes")

##################################
#             Lobbies            #
##################################

class LobbyRegistry(Base):
    __tablename__ = 'Lobby_Registry'
    UniqueID = Column(Integer, primary_key = True, autoincrement = True)
    appID = Column(Integer)
    type = Column(Integer)
    flags = Column(Integer)
    owner_accountID = Column(Integer, ForeignKey('friends_registry.accountID'))
    cellID = Column(Integer)
    public_ip = Column(BigInteger)
    members_max = Column(Integer)
    # Relationships
    members = relationship("LobbyMembers", backref = "lobby", cascade = "all, delete-orphan")

class LobbyMembers(Base):
    __tablename__ = 'Lobby_Members'
    UniqueID = Column(Integer, primary_key = True, autoincrement = True)
    LobbyID = Column(Integer, ForeignKey('Lobby_Registry.UniqueID'))
    friendRegistryID = Column(Integer, ForeignKey('friends_registry.accountID'))
    #nickname = Column(String(256))
    relation = Column(Integer)
    __table_args__ = (UniqueConstraint('LobbyID', 'friendRegistryID'),)


##################################
#           LeaderBoard          #
##################################

class LeaderboardRegistry(Base):
    __tablename__ = 'Leaderboard_Registry'
    UniqueID = Column(Integer, primary_key = True, autoincrement = True)
    appID = Column(Integer)
    name = Column(String(256))
    sort_method = Column(Integer)
    display_type = Column(Integer)
    __table_args__ = (UniqueConstraint('appID', 'name'),)


class LeaderboardEntry(Base):
    __tablename__ = 'Leaderboard_Entry'
    UniqueID = Column(Integer, primary_key = True, autoincrement = True)
    LeaderboardID = Column(Integer, ForeignKey('Leaderboard_Registry.UniqueID'))
    friendRegistryID = Column(Integer, ForeignKey('friends_registry.accountID'))
    rank = Column(Integer)
    score = Column(Integer)
    time = Column(Integer)
    details = Column(BLOB)
    ugcID = Column(Integer)
    __table_args__ = (UniqueConstraint('friendRegistryID', 'LeaderboardID'),)


class RichPresence(Base):
    __tablename__ = 'Rich_Presence'
    UniqueID = Column(Integer, primary_key = True, autoincrement = True)
    friendRegistryID = Column(Integer, ForeignKey('friends_registry.accountID'))
    key = Column(String(256))
    value = Column(String(256))
    __table_args__ = (UniqueConstraint('friendRegistryID', 'key'),)


class AppOwnershipTicketRegistry(Base):
    __tablename__ = 'AppOwnershipTicket_Registry'
    UniqueID = Column(Integer, primary_key = True, autoincrement = True)
    accountID = Column(Integer, ForeignKey('userregistry.UniqueID'))
    ticket_version = Column(Integer)
    flags = Column(Integer)
    TimeCreated = Column(custom_DateTime())
    TimeExpiration = Column(custom_DateTime())


class UserMachineIDRegistry(Base):
    __tablename__ = 'UserMachineID_Registry'
    UniqueID = Column(Integer, primary_key = True, autoincrement = True)
    accountID = Column(Integer, ForeignKey('userregistry.UniqueID'))
    BB3 = Column(String(256), nullable=True)   # Machine GUID
    FF2 = Column(String(256), nullable=True)   # MAC Address
    _3B3 = Column(String(256), nullable=True)  # Disk ID
    BBB = Column(String(256), nullable=True)   # BIOS Serial
    _333 = Column(String(256), nullable=True)  # Custom Data

##################################
# Start of SteamDB database dump #
##################################

class AchievementMaster(Base):
    __tablename__ = 'achievement_master'
    appID = Column(Integer, primary_key = True)
    achNumber = Column(Integer, primary_key = True)
    iconClosed = Column(String(512), nullable = False)
    iconOpen = Column(String(512), nullable = False)
    name = Column(String(512), nullable = False)
    description = Column(String(512), nullable = False)
    apiname = Column(String(512), nullable = False)

class AchievementPercent(Base):
    __tablename__ = 'achievement_percent'
    appID = Column(Integer, primary_key = True)
    achNumber = Column(Integer, primary_key = True)
    percent = Column(DECIMAL(6, 3), nullable = False)

class AppDescription(Base):
    __tablename__ = 'app_description'
    appID = Column(Integer, primary_key = True)
    description = Column(Text(25000), nullable = False)

class AppDevelopers(Base):
    __tablename__ = 'app_developers'
    appID = Column(Integer, primary_key = True)
    developer = Column(String(255), primary_key = True, nullable = False)

class AppGenres(Base):
    __tablename__ = 'app_genres'
    appID = Column(Integer, primary_key = True)
    genre = Column(String(50), primary_key = True, nullable = False)

class AppPublishers(Base):
    __tablename__ = 'app_publishers'
    appID = Column(Integer, primary_key = True)
    publisher = Column(String(255), primary_key = True, nullable = False)

class DlcList(Base):
    __tablename__ = 'dlc_list'
    appID = Column(Integer, primary_key = True)
    DLC = Column(Integer, primary_key = True)
    lastUpdate = Column(Integer, nullable = False)

class DlcMaster(Base):
    __tablename__ = 'dlc_master'
    appID = Column(Integer, primary_key = True)
    name = Column(String(255), nullable = False)
    releaseDate = Column(String(12), nullable = False)
    currency = Column(String(10), nullable = False)
    price = Column(Integer, nullable = False)
    age = Column(Integer, nullable = False)
    website = Column(String(255), nullable = False)

class GameMaster(Base):
    __tablename__ = 'game_master'
    appID = Column(Integer, primary_key = True)
    name = Column(String(255), nullable = False)
    releaseDate = Column(String(12), nullable = False)
    metacritic = Column(Integer, nullable = False)
    currency = Column(String(10), nullable = False)
    price = Column(Integer, nullable = False)
    recommendation = Column(Integer, nullable = False)
    age = Column(Integer, nullable = False)
    achievements = Column(Integer, nullable = False)
    website = Column(String(255), nullable = False)

class PackageList(Base):
    __tablename__ = 'package_list'
    packageID = Column(Integer, primary_key = True)
    appID = Column(Integer, primary_key = True)

class RandomList(Base):
    __tablename__ = 'random_list'
    appID = Column(Integer, primary_key = True)

####################################
#      Purchase Related Tables     #
####################################
class Steam3LicenseRecord(Base):
    __tablename__ = 'steam3_license_record'
    UniqueID = Column(Integer, primary_key = True, autoincrement = True)
    AccountID = Column(Integer, ForeignKey('userregistry.UniqueID'))
    PackageID = Column(Integer)
    LicenseKey = Column(String(256))
    DateAdded = Column(custom_DateTime())
    LicenseFlags = Column(Integer)
    LicenseType = Column(Integer)
    PaymentType = Column(Integer)
    PurchaseCountryCode = Column(String(2))
    TimeLimit = Column(Integer)
    MinutesUsed = Column(Integer)
    TimeNextProcess = Column(Integer)
    ChangeNumber = Column(Integer)
    OwnerAccountID = Column(Integer)
    InitialPeriod = Column(Integer)
    InitialTimeUnit = Column(Integer)
    RenewalPeriod = Column(Integer)
    RenewalTimeUnit = Column(Integer)
    AccessToken = Column(Integer)
    MasterPackageID = Column(Integer)


class ExternalPurchaseInfoRecord(Base):
    """For paypal and maybe 1 click payments"""
    __tablename__ = 'external_purchase_record'
    UniqueID = Column(Integer, primary_key=True, autoincrement=True)
    AccountID = Column(Integer, ForeignKey('userregistry.UniqueID'))
    PackageID = Column(Integer)
    TransactionType = Column(Integer)
    TransactionData = Column(String(20))
    DateAdded = Column(custom_DateTime())


class Steam3TransactionsRecord(Base):
    __tablename__ = 'steam3_transactions_record'

    # UniqueID is a 64-bit GlobalID generated by GlobalIDGenerator
    UniqueID = Column(BigInteger, primary_key=True, autoincrement=False)
    AccountID = Column(Integer, ForeignKey('userregistry.UniqueID'))
    PaymentType = Column(Integer)  # e.g. CC, PayPal, CD?Key, etc.
    PaymentEntryID = Column(Integer)  # Points to Steam3CCRecord if CC, or external purchase, etc.

    PackageID = Column(Integer)  # The purchased subscription

    # Gift fields merged here:
    GifterAccountID = Column(Integer, nullable=True)
    GifteeEmail = Column(String(256), nullable=True)
    GifteeAccountID = Column(String(256), nullable=True)
    GiftMessage = Column(String(512), nullable=True)
    GifteeName = Column(String(256), nullable=True)
    Sentiment = Column(String(256), nullable=True)
    Signature = Column(String(256), nullable=True)

    AddressEntryID = Column(Integer, ForeignKey('steam3_transaction_address_record.UniqueID'), nullable=True)
    ShippingEntryID = Column(Integer, ForeignKey('steam3_transaction_address_record.UniqueID'), nullable=True)

    LicenseEntryID = Column(Integer, ForeignKey('steam3_license_record.UniqueID'), nullable=True)
    TransactionDate = Column(custom_DateTime())
    DateCompleted = Column(custom_DateTime(), nullable=True)
    DateCancelled = Column(custom_DateTime(), nullable=True)
    DateAcknowledged = Column(custom_DateTime(), nullable=True)

    BaseCostInCents = Column(Integer)
    DiscountsInCents = Column(Integer)
    TaxCostInCents = Column(Integer)
    ShippingCostInCents = Column(Integer, default=0)

    PassInformation = Column(JSON, nullable=False, default={})

    # Relationship to track multiple passes via a junction table:
    guest_passes = relationship("TransactionGuestPasses", back_populates="transaction")

    def __repr__(self):
        return f"<Steam3TransactionsRecord(UniqueID={self.UniqueID}, " \
               f"AccountID={self.AccountID}, GifterAccountID={self.GifterAccountID}, " \
               f"GifteeAccountID={self.GifteeAccountID}, ...)>"


class Steam3TransactionAddressRecord(Base):
    __tablename__ = 'steam3_transaction_address_record'
    UniqueID = Column(Integer, primary_key = True, autoincrement = True)
    AccountID = Column(Integer, ForeignKey('userregistry.UniqueID'))
    Name = Column(String(256))
    Address1 = Column(String(256))
    Address2 = Column(String(256))
    City = Column(String(256))
    PostCode = Column(String(25))
    State = Column(String(256))
    CountryCode = Column(String(5))
    Phone = Column(String(256))


class Steam3CCRecord(Base):
    """ Used to hold all other payment types besides paypal and oneclick"""
    __tablename__ = 'steam3_cc_record'
    UniqueID = Column(Integer, primary_key = True, autoincrement = True)
    AccountID = Column(Integer, ForeignKey('userregistry.UniqueID'))
    CardType = Column(Integer)
    CardNumber = Column(String(256))
    CardHolderName = Column(String(256))
    CardExpYear = Column(Integer)
    CardExpMonth = Column(Integer)
    CardCVV2 = Column(Integer)
    #BillingAddressEntryID = Column(Integer, ForeignKey('steam3_transaction_address_record.UniqueID'), nullable = True)
    DateAdded = Column(custom_DateTime())


class TransactionGuestPasses(Base):
    __tablename__ = 'TransactionGuestPasses'
    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(BigInteger, ForeignKey('steam3_transactions_record.UniqueID'))
    guest_pass_id = Column(Integer, ForeignKey('GuestPasses_Registry.UniqueID'))

    # Optional: Establish relationships for easy navigation
    transaction = relationship("Steam3TransactionsRecord", back_populates="guest_passes")
    guest_pass = relationship("GuestPassRegistry")

class GuestPassRegistry(Base):
    """
    Registry for guest passes and gift passes.

    Guest passes are temporary licenses that can be sent to friends.
    Gift passes are permanent licenses that can be gifted.

    The pass type is determined by the billing type of the target subscription:
    - BillingType 4 (GuestPass): Temporary, time-limited
    - BillingType 6 (Gift): Permanent gift

    Extended info keys from the subscription determine pass behavior:
    - GrantExpirationDays: Days until the pass expires if not sent
    - GrantPassesCount: Number of passes granted
    - InitialPeriod: Duration of the pass once activated
    - InitialTimeUnit: Unit for InitialPeriod (Day, Week, etc.)
    """
    __tablename__ = 'GuestPasses_Registry'
    UniqueID = Column(Integer, primary_key = True, autoincrement = True)
    PackageID = Column(Integer)  # The subscription/package this pass grants
    SourcePackageID = Column(Integer, nullable = True)  # The subscription that created this pass
    TimeCreated = (custom_DateTime())
    TimeExpiration = (custom_DateTime())  # When the pass expires for sending
    TimeSent = Column(Integer, nullable = True)  # Unix timestamp when sent (0 if not sent)
    TimeAcked = Column(Integer, nullable = True)  # Unix timestamp when acknowledged (0 if not)
    TimeRedeemed = Column(Integer, nullable = True)  # Unix timestamp when redeemed (0 if not)
    TimeActivationExpires = (custom_DateTime())  # When the activated pass expires (for guest passes)
    Sent = Column(Integer, nullable = True, default = 0)  # Legacy: 1 if sent, 0 otherwise
    Acked = Column(Integer, nullable = True, default = 0)  # Legacy: 1 if acknowledged
    Redeemed = Column(Integer, nullable = True, default = 0)  # Legacy: 1 if redeemed
    RecipientAddress = Column(String(256), nullable = True)  # Email address of recipient
    RecipientAccountID = Column(Integer, ForeignKey('userregistry.UniqueID'), nullable = True)
    SenderAddress = Column(String(256), nullable = True)  # Email address of sender
    SenderName = Column(String(256), nullable = True)  # Display name of sender
    PassTimeLimit = Column(Integer)  # InitialPeriod value
    PassTimeLimitUnit = Column(String(10))  # InitialTimeUnit value
    AppIDOwnedRequirement = Column(Integer)  # AppID that must be owned for this pass
    # SenderAccountID will ALWAYS be set, but if sent is null/0
    # then we send an empty string in the guestpass packet
    SenderAccountID = Column(Integer, ForeignKey('userregistry.UniqueID'), nullable = True)
    # Pass type: 0 = GuestPass (temp), 1 = Gift (permanent)
    PassType = Column(Integer, nullable = True, default = 0)
    # State: 0 = Available, 1 = Sent, 2 = Acked, 3 = Redeemed, 4 = Expired, 5 = Revoked
    State = Column(Integer, nullable = True, default = 0)
    # Gift-specific fields
    GiftMessage = Column(Text, nullable = True)  # Personal message with gift
    Signature = Column(String(256), nullable = True)  # Gift card signature
    Sentiment = Column(String(256), nullable = True)  # Gift card sentiment


class PendingSystemIM(Base):
    """
    Queue for SystemIM messages that need to be delivered when a user comes online.

    When a user is offline and an event occurs that requires a SystemIM notification
    (guest pass received, gift revoked, etc.), we store it here and deliver when
    they log in.
    """
    __tablename__ = 'pending_system_im'
    UniqueID = Column(Integer, primary_key = True, autoincrement = True)
    RecipientAccountID = Column(Integer, ForeignKey('userregistry.UniqueID'), nullable = False)
    MessageType = Column(Integer, nullable = False)  # SystemIMType enum value
    MessageBody = Column(Text, nullable = True)  # Message text
    MessageID = Column(BigInteger, nullable = True)  # Unique message identifier
    AckRequired = Column(Integer, default = 1)  # Whether acknowledgment is required
    TimeCreated = (custom_DateTime())
    Delivered = Column(Integer, default = 0)  # 1 if delivered, 0 if pending
    TimeDelivered = (custom_DateTime())  # When the message was delivered
    # Optional reference to related guest pass
    GuestPassID = Column(Integer, ForeignKey('GuestPasses_Registry.UniqueID'), nullable = True)

# FIXME this is not needed, we store the gift/guest pass information in the transaction table
"""class TemporaryPasses(Base):
    __tablename__ = 'temporary_passes'
    UniqueID = Column(Integer, primary_key=True, autoincrement=True)
    AccountID = Column(Integer, ForeignKey('userregistry.UniqueID'), nullable=False)
    TransactionID = Column(Integer, nullable=False)
    PassInformation = Column(JSON, nullable=False)

    def __repr__(self):
        return (
            f"<TemporaryPasses(id={self.id}, "
            f"user_id={self.user_id}, "
            f"transactionID={self.transactionID}, "
            f"passes_json={self.passes_json})>"
        )"""

class CountryTax(Base):
    __tablename__ = 'country_tax'
    id = Column(Integer, primary_key=True, autoincrement=True)
    country = Column(String(255), nullable=False)
    tax_rate = Column(DECIMAL(5, 2), nullable=False)

class StateSalesTax(Base):
    __tablename__ = 'state_sales_tax'
    id = Column(Integer, primary_key=True, autoincrement=True)
    state = Column(String(2), nullable=False)  # Two-letter abbreviation
    tax_rate = Column(DECIMAL(5, 2), nullable=False)


class S3SurveyData(Base):
    __tablename__ = 'steam3_survey_data'
    uniqueID = Column(Integer, primary_key=True, autoincrement=True)
    # Columns based on WizardData variables
    NetSpeed = Column(Integer)
    NetSpeedLabel = Column(String(255))
    Microphone = Column(Integer)
    MicrophoneLabel = Column(String(255))
    CPUVendor = Column(String(255))
    CPUSpeed = Column(Integer)
    LogicalProcessors = Column(Integer)
    PhysicalProcessors = Column(Integer)
    HyperThreading = Column(Integer)
    FCMOV = Column(Integer)
    SSE2 = Column(Integer)
    SSE3 = Column(Integer)
    SSE4 = Column(Integer)
    SSE4a = Column(Integer)
    SSE41 = Column(Integer)
    SSE42 = Column(Integer)
    OSVersion = Column(String(255))
    Is64BitOS = Column(Integer)
    OSType = Column(Integer)
    NTFS = Column(Integer)
    AdapterDescription = Column(String(255))
    DriverVersion = Column(String(255))
    DriverDate = Column(String(255))
    VRAMSize = Column(Integer)
    BitDepth = Column(Integer)
    RefreshRate = Column(Integer)
    NumMonitors = Column(Integer)
    NumDisplayDevices = Column(Integer)
    MonitorWidthInPixels = Column(Integer)
    MonitorHeightInPixels = Column(Integer)
    DesktopWidthInPixels = Column(Integer)
    DesktopHeightInPixels = Column(Integer)
    MonitorWidthInMillimeters = Column(Integer)
    MonitorHeightInMillimeters = Column(Integer)
    MonitorDiagonalInMillimeters = Column(Integer)
    VideoCard = Column(String(255))
    DXVideoCardDriver = Column(String(255))
    DXVideoCardVersion = Column(String(255))
    DXVendorID = Column(Integer)
    DXDeviceID = Column(Integer)
    MSAAModes = Column(String(255))
    MultiGPU = Column(Integer)
    NumSLIGPUs = Column(Integer)
    DisplayType = Column(Integer)
    BusType = Column(Integer)
    BusRate = Column(Integer)
    dell_oem = Column(Integer)
    AudioDeviceDescription = Column(String(255))
    RAM = Column(Integer)
    LanguageId = Column(Integer)
    DriveType = Column(Integer)
    TotalHD = Column(BigInteger)
    FreeHD = Column(BigInteger)
    SteamHDUsage = Column(Integer)
    OSInstallDate = Column(String(255))
    GameController = Column(String(255))
    NonSteamApp_firefox = Column(Integer)
    NonSteamApp_openoffice = Column(Integer)
    NonSteamApp_wfw = Column(Integer)
    NonSteamApp_za = Column(Integer)
    NonSteamApp_f4m = Column(Integer)
    NonSteamApp_cog = Column(Integer)
    NonSteamApp_pd = Column(Integer)
    NonSteamApp_vmf = Column(Integer)
    NonSteamApp_grl = Column(Integer)
    NonSteamApp_fv = Column(Integer)
    machineid = Column(BigInteger)
    version = Column(Integer)
    country = Column(String(255))
    ownership = Column(String(255))

# ORM table classes
class CserEvents(Base):
    __tablename__ = 'cser_events'
    id         = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(32))
    event_time = Column(DateTime)
    data       = Column(JSON)


class SurveyRaw(Base):
    __tablename__ = 'survey_raw'
    id   = Column(Integer, primary_key=True, autoincrement=True)
    ts   = Column(DateTime)
    data = Column(JSON)


class SurveyTotals(Base):
    __tablename__ = 'survey_totals'
    field        = Column(String(64),  primary_key=True)
    option_value = Column(String(128), primary_key=True)
    count        = Column(Integer)


class GameplayUsers(Base):
    __tablename__ = 'gameplay_users'
    day     = Column(Date,      primary_key=True)
    game    = Column(String(64), primary_key=True)
    user_id = Column(BigInteger, primary_key=True)


class UserStats(Base):
    __tablename__ = 'user_stats'
    user_id = Column(BigInteger, primary_key=True)
    app_id  = Column(Integer,    primary_key=True)
    stat    = Column(String(128), primary_key=True)
    value   = Column(String(256))


class ContentLoad(Base):
    __tablename__ = 'content_load'
    day      = Column(Date,      primary_key=True)
    server   = Column(String(64), primary_key=True)
    starts   = Column(Integer,    default=0)
    finishes = Column(Integer,    default=0)


class AdminAudit(Base):
    __tablename__ = 'admin_audit'
    id      = Column(Integer,   primary_key=True, autoincrement=True)
    admin   = Column(String(64))
    action  = Column(String(64))
    payload = Column(JSON)
    ts      = Column(DateTime)


class ScheduledRestarts(Base):
    __tablename__ = 'scheduled_restarts'
    id           = Column(Integer, primary_key=True, autoincrement=True)
    server_id    = Column(String(64))
    restart_time = Column(DateTime)


class AdministrationUsersRecord(Base):
    """Administrator login information."""
    __tablename__ = 'admin_users_record'

    UniqueID = Column(Integer, primary_key=True, autoincrement=True)
    # Store the admin's username directly instead of referencing userregistry.
    Username = Column(String(60), nullable=False, unique=True)
    # 64 character SHA-256 hex digest
    PWHash = Column(String(64), nullable=False)
    PWSeed = Column(String(256))
    Rights = Column(Integer)


class PlatformUpdateNews(Base):
    __tablename__ = 'platform_update_news'

    id = Column(Integer, primary_key = True, autoincrement = True)
    date = Column(Date, nullable = False)
    title = Column(String(255), nullable = False)
    content = Column(Text, nullable = False)

class CommunityAppIcons(Base):
    __tablename__ = 'community_appicons'

    UniqueID = Column(Integer, primary_key=True, autoincrement=True)
    AppID = Column(Integer, nullable=False)
    Icon = Column(Text, nullable=True)
    Logo = Column(Text, nullable=True)
    LogoSmall = Column(Text, nullable=True)


class StmserverSettings(Base):
    __tablename__ = 'stmserver_settings'

    setting = Column(String(255), primary_key=True)
    value = Column(Text)


class LegacyGameKeys(Base):
    __tablename__ = 'LegacyGameKeys'

    AppID = Column(Integer, primary_key=True)
    GameKey = Column(String(64), primary_key=True)
    SteamID = Column(BigInteger, nullable=True)


class UserStatsData(Base):
    """User statistics data for games"""
    __tablename__ = 'user_stats_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    steam_id = Column(BigInteger, nullable=False)
    app_id = Column(Integer, nullable=False)
    stat_id = Column(SmallInteger, nullable=False)
    stat_value = Column(Integer, nullable=False)
    last_updated = Column(custom_DateTime, nullable=False)
    
    # Composite unique constraint for steam_id, app_id, stat_id
    __table_args__ = (UniqueConstraint('steam_id', 'app_id', 'stat_id', name='_user_stat_constraint'),)


class UserAchievements(Base):
    """User achievement data for games"""
    __tablename__ = 'user_achievements'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    steam_id = Column(BigInteger, nullable=False)
    app_id = Column(Integer, nullable=False)
    stat_id = Column(SmallInteger, nullable=False)  # Achievement stat ID
    bit_position = Column(SmallInteger, nullable=False)  # Bit position in the achievement stat
    achieved_at = Column(Integer, nullable=False)  # Unix timestamp when achieved
    last_updated = Column(custom_DateTime, nullable=False)
    
    # Composite unique constraint for steam_id, app_id, stat_id, bit_position
    __table_args__ = (UniqueConstraint('steam_id', 'app_id', 'stat_id', 'bit_position', name='_user_achievement_constraint'),)


class UserStatsCache(Base):
    """Cache metadata for user stats"""
    __tablename__ = 'user_stats_cache'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    steam_id = Column(BigInteger, nullable=False)
    app_id = Column(Integer, nullable=False)
    crc = Column(Integer, nullable=False)
    pending_changes = Column(Integer, default=0)
    schema_version = Column(Integer, nullable=True)
    last_updated = Column(custom_DateTime, nullable=False)
    
    # Composite unique constraint for steam_id, app_id
    __table_args__ = (UniqueConstraint('steam_id', 'app_id', name='_user_stats_cache_constraint'),)


# Modern Chat Group System (Discord-like structure)
class ChatRoomGroup(Base):
    """Chat room groups with roles and channels"""
    __tablename__ = 'chat_room_group'
    
    group_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    owner_id = Column(BigInteger, nullable=False)
    tagline = Column(String(255), default='')
    default_chat_id = Column(Integer, nullable=True)
    default_role_id = Column(Integer, nullable=True)
    clan_id = Column(BigInteger, nullable=True)  # Associated clan
    avatar_id = Column(LargeBinary, nullable=True)
    created_at = Column(custom_DateTime, nullable=False, default=datetime.now)
    
    # Relationships
    chats = relationship("ChatRoomGroupChat", back_populates="group", cascade="all, delete-orphan")
    roles = relationship("ChatRoomGroupRole", back_populates="group", cascade="all, delete-orphan")


class ChatRoomGroupChat(Base):
    """Individual chats within groups"""
    __tablename__ = 'chat_room_group_chat'
    
    chat_id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey('chat_room_group.group_id'), nullable=False)
    name = Column(String(255), nullable=False)
    voice_allowed = Column(Boolean, default=False)
    ordinal = Column(Integer, default=0)
    
    # Relationships
    group = relationship("ChatRoomGroup", back_populates="chats")


class ChatRoomGroupRole(Base):
    """Role-based permissions for chat groups"""
    __tablename__ = 'chat_room_group_role'
    
    role_id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey('chat_room_group.group_id'), nullable=False)
    name = Column(String(255), nullable=False)
    clan_rank = Column(Integer, nullable=True)
    ordinal = Column(Integer, default=0)
    
    # Permission flags
    can_create_rename_delete_channel = Column(Boolean, default=False)
    can_kick = Column(Boolean, default=False)
    can_ban = Column(Boolean, default=False)
    can_invite = Column(Boolean, default=True)
    can_change_tagline_avatar_name = Column(Boolean, default=False)
    can_chat = Column(Boolean, default=True)
    can_view_history = Column(Boolean, default=True)
    can_change_group_roles = Column(Boolean, default=False)
    can_change_user_roles = Column(Boolean, default=False)
    can_mention_all = Column(Boolean, default=True)
    can_set_watching_broadcast = Column(Boolean, default=True)
    
    # Relationships
    group = relationship("ChatRoomGroup", back_populates="roles")


# Enhanced Lobby System with Search Views
class LobbySearchView(Base):
    """View for efficient lobby searching and member counting"""
    __tablename__ = 'lobby_search_view'
    __table_args__ = {'info': {'is_view': True}}
    
    lobby_id = Column(Integer, primary_key=True)
    app_id = Column(Integer)
    type = Column(Integer)
    flags = Column(Integer)
    owner_id = Column(BigInteger)
    cell_id = Column(Integer)
    public_ip = Column(BigInteger)
    members_max = Column(Integer)
    members_count = Column(Integer)
    available_slots = Column(Integer)


# Enhanced Clan Permission Tables
class ClanPermissionTemplate(Base):
    """Templates for default clan permission sets"""
    __tablename__ = 'clan_permission_template'
    
    template_id = Column(Integer, primary_key=True, autoincrement=True)
    template_name = Column(String(50), nullable=False, unique=True)
    permission_edit_profile = Column(Integer, default=0)
    permission_make_officer = Column(Integer, default=0)
    permission_add_event = Column(Integer, default=0)
    permission_choose_potw = Column(Integer, default=0)
    permission_invite_member = Column(Integer, default=0)
    permission_kick_member = Column(Integer, default=0)


# Event System Enhancement
class ClanEventAttendance(Base):
    """Track clan event attendance"""
    __tablename__ = 'clan_event_attendance'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey('community_clan_events.eventID'), nullable=False)
    player_id = Column(BigInteger, nullable=False)
    attendance_status = Column(Integer, default=0)  # 0=maybe, 1=yes, 2=no
    timestamp = Column(custom_DateTime, nullable=False, default=datetime.now)
    
    __table_args__ = (UniqueConstraint('event_id', 'player_id', name='_event_attendance_constraint'),)


# Lobby Metadata System Tables
class LobbyMetadata(Base):
    """Store lobby key-value metadata"""
    __tablename__ = 'lobby_metadata'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    lobby_steam_id = Column(BigInteger, nullable=False)
    metadata_key = Column(String(255), nullable=False)
    metadata_value = Column(Text)
    
    __table_args__ = (
        UniqueConstraint('lobby_steam_id', 'metadata_key', name='_lobby_metadata_uk'),
    )


class LobbyMemberMetadata(Base):
    """Store per-member lobby metadata"""
    __tablename__ = 'lobby_member_metadata'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    lobby_steam_id = Column(BigInteger, nullable=False)
    member_steam_id = Column(BigInteger, nullable=False)
    metadata_key = Column(String(255), nullable=False)
    metadata_value = Column(Text)
    
    __table_args__ = (
        UniqueConstraint('lobby_steam_id', 'member_steam_id', 'metadata_key', name='_lobby_member_metadata_uk'),
    )


class LobbyGameServers(Base):
    """Store lobby to game server bindings"""
    __tablename__ = 'lobby_game_servers'
    
    lobby_steam_id = Column(BigInteger, primary_key=True)
    server_ip = Column(Integer, nullable=False)
    server_port = Column(SmallInteger, nullable=False)
    server_steam_id = Column(BigInteger, nullable=True)


class LobbyChatHistory(Base):
    """Store lobby chat message history"""
    __tablename__ = 'lobby_chat_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    lobby_steam_id = Column(BigInteger, nullable=False)
    message_id = Column(Integer, nullable=False)
    sender_steam_id = Column(BigInteger, nullable=False)
    message_text = Column(Text, nullable=False)
    chat_entry_type = Column(SmallInteger, default=1)  # 1=ChatMsg, 2=Typing, 3=InviteGame, etc
    timestamp = Column(custom_DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        UniqueConstraint('lobby_steam_id', 'message_id', name='_lobby_chat_uk'),
    )


##################################
#        FTP Server Tables       #
##################################

class AwaitingReview(Base):
    """Stores pending FTP uploads that require administrative review."""
    __tablename__ = 'awaiting_review'
    id = Column(Integer, primary_key=True, autoincrement=True)
    appid = Column(String(50), nullable=False, unique=True)
    uploader = Column(String(100), nullable=False)
    upload_datetime = Column(String(50), nullable=False)  # Stored as string in "%m/%d/%Y %H:%M:%S"
    total_size = Column(Integer, nullable=False, default=0)
    uploader_ip = Column(String(50), nullable=False)
    uploader_port = Column(String(10), nullable=False)
    file_paths = Column(Text, nullable=True)  # File paths separated by '|'
    app_names = Column(Text, nullable=True)  # Comma-separated app names from XML
    subscriptions = Column(Text, nullable=True)  # Subscription info: "id:name|id:name|..."


class FileOwnership(Base):
    """Records the file ownership for each file uploaded via FTP."""
    __tablename__ = 'file_ownership'
    id = Column(Integer, primary_key=True, autoincrement=True)
    uploader = Column(String(100), nullable=False)
    appid = Column(String(50), nullable=False)
    file_path = Column(Text, nullable=False)
    upload_datetime = Column(String(50), nullable=False)
    file_size = Column(Integer, nullable=False)


class FTPAdminActionLog(Base):
    """Logs admin actions for FTP uploads (approval or denial)."""
    __tablename__ = 'ftp_admin_action_log'
    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_username = Column(String(100), nullable=False)
    admin_ip = Column(String(50), nullable=False)
    appid = Column(String(50), nullable=False)
    action = Column(String(20), nullable=False)  # e.g., "APPROVE", "DENY"
    details = Column(Text, nullable=True)
    timestamp = Column(String(50), nullable=False)


class ApprovedApplication(Base):
    """Stores approved applications for management after approval."""
    __tablename__ = 'approved_applications'
    id = Column(Integer, primary_key=True, autoincrement=True)
    appid = Column(String(50), nullable=False, unique=True)
    app_names = Column(Text, nullable=True)  # Comma-separated app names
    subscriptions = Column(Text, nullable=True)  # Subscription info: "id:name|id:name|..."
    xml_file_path = Column(Text, nullable=True)  # Path to the XML file for this app
    approval_datetime = Column(String(50), nullable=False)
    approved_by = Column(String(100), nullable=False)
    last_modified = Column(String(50), nullable=True)
    modified_by = Column(String(100), nullable=True)


class FTPUser(Base):
    """Stores FTP user accounts in the database."""
    __tablename__ = 'ftp_users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), nullable=False, unique=True)
    password = Column(String(255), nullable=False)  # Plain text or hashed
    permissions = Column(String(50), nullable=False, default='r')  # r=read, w=write, d=delete, u=upload
    home_directory = Column(String(500), nullable=True)  # Custom home dir, or None for default
    is_locked = Column(Boolean, nullable=False, default=False)
    quota_mb = Column(Integer, nullable=True, default=0)  # Storage quota in MB (0 = unlimited)
    bandwidth_kbps = Column(Integer, nullable=True, default=0)  # Bandwidth limit in KB/s (0 = unlimited)
    created_datetime = Column(String(50), nullable=False)
    created_by = Column(String(100), nullable=True)
    last_login = Column(String(50), nullable=True)
    login_count = Column(Integer, nullable=False, default=0)


class MarketingMessages(Base):
    """Stores marketing message content for Steam client popups."""
    __tablename__ = 'MarketingMessages'
    GID = Column(BigInteger, primary_key=True, autoincrement=False)
    DATETIME = Column(DateTime, nullable=False, index=True, server_default=text('CURRENT_TIMESTAMP'))
    HTML = Column(Text, nullable=False)


class EmulatorDBVersion(Base):
    """Stores the current database version."""
    __tablename__ = 'version'
    db_ver = Column(Integer, primary_key=True, autoincrement=False)



