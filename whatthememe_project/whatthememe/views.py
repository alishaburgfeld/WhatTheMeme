from glob import glob
from django.shortcuts import render
from django.core import serializers
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.contrib.auth import authenticate, login, logout
from .models import AppUser as User
from .models import FriendList, FriendRequest, Game, Game_User, Game_Card
from rest_framework.decorators import api_view
from django.forms.models import model_to_dict
from django.contrib.auth.decorators import login_required
import requests
import random
import json
from dotenv import load_dotenv
import os


load_dotenv()

cards = []
memes = []
# cardCount = 0

def index(request):
    print('home!')
    theIndex = open('static/index.html').read()
    return HttpResponse(theIndex)

def getUser(user_email):
    user = User.objects.get(email = user_email)
    return user

#api call
def getCards():
    global cards
    url = "https://cards-against-humanity.p.rapidapi.com/white/25"
    headers = {
        "X-RapidAPI-Key": os.environ['X-RapidAPI-Key'],
        "X-RapidAPI-Host": "cards-against-humanity.p.rapidapi.com"
    }
    response = requests.request("GET", url, headers=headers)
    JSON_response = json.loads(response.text)
    # JSON_response is an array of objects, the value for key "text" is what I want.
    for card in JSON_response:
        cards.append(card['text'])


def getMemes():
    # returns about 100 memes in an array
    global memes
    url = 'https://api.imgflip.com/get_memes'
    response = requests.request('GET', url)
    JSON_response = json.loads(response.text)
    memeArray = JSON_response['data']['memes']
    for meme in memeArray:
        memes.append(meme['url'])

@api_view(['GET'])
def get_meme_card(request):
    # print('IN GET MEME GET REQUEST ON DJANGO')
    user = getUser(request.user.email)
    # game_user = game_user = Game_User.objects.get(player = user)
    # running into issue of returning more than one.
    game_user = Game_User.objects.filter(player = user)
    print('LINE 60 GAME USER', game_user)
    game_1 = game_user[len(game_user)-1].game
    round = game_1.round
    getMemes()
    if memes:
        try:
            return JsonResponse({'success': True, 'memes':memes, 'round': round})
        except Exception as e:
            return JsonResponse({'success': False, 'reason': str(e)})
    else:
        return JsonResponse({'success': False, 'reason': 'no memes available'})


@api_view(['POST'])
def sign_up(request):
    user_email=request.data['email']
    print('user email is', user_email)
    try:
        print('inside the try')
        all_users = User.objects.all()
        all_user_emails=[]
        for user in all_users:
            all_user_emails.append(user.email)
        if user_email in all_user_emails:
            return JsonResponse({'success': "False", 'reason': 'This email already exists, please log-in'})
        else:
            print('inside sign up else')
            newUser = User.objects.create_user(username=request.data['email'], password=request.data['password'], email=request.data['email'])
            newUser.full_clean
            newUser.save()
            list= FriendList(user = newUser)
            list.full_clean
            list.save()
            print('new user is', newUser)
            return JsonResponse({'success': "True"})
    except Exception as e:
        return JsonResponse({'success': "False", 'reason': str(e)})

@api_view(['POST'])
def log_in(request):
    # this will use the django framework request which will allow us to not use request.body.___ and we won't have to do json.loads(request.body)
    # print(dir(request))
    # this will give us the original request not the django rest framework request version
    # print(dir(request._request))
    #built in python function for printing keys in request

    # DRF assumes that the body is JSON, and automatically parses it into a dictionary at request.data
    email = request.data['email']
    password = request.data['password']
    # user = authenticate(username=email, password=password, email=email)
    user = authenticate(username=email, password=password)
    if user is not None:
        if user.is_active:
            try:
                # access the base request, not the DRF request
                # this starts a login session for this user
                login(request._request, user)
                print(f"{email} IS LOGGED IN!!!!!!!!!")
                return JsonResponse({'success': "True"}) 
            except Exception as e:
                return JsonResponse({'success': "False", 'reason': f'failed to login, {str(e)}'})
        else:
            return JsonResponse({'success': "False", 'reason': 'This account has been disabled, please sign-up again'})
    else:
        return JsonResponse({'success': "False", 'reason': "This account doesn't exist, please sign-up"})    


@api_view(['POST'])
def log_out(request):
    user_email= request.user.email
    user = getUser(user_email)
    game_user_objects = Game_User.objects.filter(player = user)
    try:
        logout(request)
        return JsonResponse({'success': True, 'action': 'logged out'})
    except Exception as e:
            return JsonResponse({'success': False, 'reason': f'something went wrong {str(e)}'})


@api_view(['PUT'])
def delete_game_user(request):
    user_email= request.data['user']
    print('IN DELETE GAME USER LINE 133, USER EMAIL', user_email)
    user = getUser(user_email)
    game_user_objects = Game_User.objects.filter(player = user)
    try:
        game_user_objects.delete()
        print('GAME USER SHOULD BE DELETED LINE 126', game_user_objects)
        return JsonResponse({'success': True, 'action': 'user deleted'})
    except Exception as e:
            return JsonResponse({'success': False, 'reason': f'something went wrong {str(e)}'})

@api_view(['GET'])
def who_am_i(request):
    if request.user.is_authenticated:
        user = getUser(request.user.email)
        try:
            game_user = Game_User.objects.get(player = user)
            if game_user:
                return JsonResponse({'email': request.user.email, 'game_user': True})
        except:
            return JsonResponse({'email': request.user.email, 'game_user': False})
    else:
        return JsonResponse({'user':None})

#once friends request is approved I will add them to each other's lists
@api_view(['PUT'])
@login_required
def add_friend(request): #accepts a friend request
    user_email = request.user.email
    friend_email = request.data['friend_email']
    user = User.objects.get(email = user_email)
    userFList = FriendList.objects.get(user = user)
    friend = User.objects.get(email = friend_email)
    friendFList = FriendList.objects.get(user = friend)
    if friend not in user.friends.all():
        if friend != None:
            try:
                # wrong syntax: user.friends.add(friend)
                userFList.friends.add(friend)
                friendFList.friends.add(user)
                friend_request = FriendRequest.objects.get(sender = friend, receiver = user)
                friend_request.is_active = False
                # had to use update instead of save because it is a queryset
                friend_request.save()
                return JsonResponse({'success':True})
            except Exception as e:
                return JsonResponse({'success': False, 'reason': f'something went wrong {str(e)}'})
        else:
            return JsonResponse({'success': False, 'reason': 'friends account doesnt exist'})
    else:
        return JsonResponse({'success': False, 'reason': 'friend is already in friend list'})


@api_view(['PUT'])
def remove_friend(request):
    user_email = request.user.email
    friend_email = request.data['friend_email']
    print('IN DELETE ON DJANGO.', user_email, 'friend', friend_email)
    user = User.objects.get(email = user_email)
    userFList = FriendList.objects.get(user = user)
    friend = User.objects.get(email = friend_email)
    friendFList = FriendList.objects.get(user = friend)
    if friend in userFList.friends.all():
        try:
            userFList.friends.remove(friend)
            friendFList.friends.remove(user)
            return JsonResponse({'success':True})
        except Exception as e:
            return JsonResponse({'success': False, 'reason': f'something went wrong {str(e)}'})
    else:
        return JsonResponse({'success': False, 'reason': 'user is not your friend'})

@api_view(['PUT'])
def create_friend_request(request):
    user_email = request.user.email
    friend_email = request.data['friend_email']
    user = User.objects.get(email = user_email)
    friend = User.objects.get(email = friend_email)
    if friend:
        try:
            friend_request = FriendRequest(sender = user, receiver = friend, is_active = True)
            friend_request.full_clean
            friend_request.save()
            return JsonResponse({'success':True})
        except:
            # if friend request already exists it will send this one
            return JsonResponse({'success': False, 'reason': 'something went wrong'})
    else:
        return JsonResponse({'success': False, 'reason': 'friends account doesnt exist'})

# this will be stretch goal
# @api_view(['POST'])
# def cancel_friend_request(request):
#     user_email = request.data['user_email']
#     friend_email = request.data['friend_email']
#     user = getUser(user_email)
#     friend = getUser(friend_email)
#     #this might be wrong syntax::
#     friend_request = FriendRequest.get(sender = user, receiver= friend)
#     if friend_request != None:
#         try:
#             friend_request.delete()
#             return JsonResponse({'success':True})
#         except:
#             return JsonResponse({'success': False, 'reason': 'something went wrong'})
#     else:
#         return JsonResponse({'success': False, 'reason': 'friend request doesnt exist'})

# this shows the user any friend requests that started from somebody else requesting they become their friend
@api_view(['GET'])
def view_friend_requests(request):
    print('YOU ARE IN THE GET REQUEST ON DJANGO FOR VIEW FRIEND REQUESTS')
    user_email = request.user.email
    user = getUser(user_email)
    # view any requests sent to the user
    friend_requests = FriendRequest.objects.filter(receiver= user, is_active = True)
    if friend_requests:
        list_of_friend_requests=[]
        for item in friend_requests:
            #sends back the emails of all pending friend requests
            sender = item.sender
            list_of_friend_requests.append(sender.email)
        # print('list of friends_requests:', list_of_friend_requests)
        try:
            return JsonResponse({'friend_requests': list_of_friend_requests})
        except:
            return JsonResponse({'success': False, 'reason': 'something went wrong'})
    else:
        return JsonResponse({'success': False, 'reason': "you don't have any friend requests"})

@api_view(['GET'])
def view_friend_list(request):
    user_email = request.user.email
    user = getUser(user_email)
    # view all friends
    friends = user.friends.all()
    if len(friends)>0:
        list_of_friends=[]
        for friend in friends:
            # print(friend.id) # THIS IS THE FRIENDS LIST ID!!!!
            friend_list = FriendList.objects.get(id= friend.id)
            friend_object=friend_list.user
            friend_email = friend_object.email
            list_of_friends.append(friend_email)
            # print('dir friend', dir(friend))
        # print('list of friends line 225:', list_of_friends)
        try:
            return JsonResponse({'friends': list_of_friends})
        except:
            return JsonResponse({'success': False, 'reason': 'something went wrong'})
    else:
        return JsonResponse({'success': False, 'reason': "you don't have any friends"})

@api_view(['PUT'])
def decline_friend_request(request):
    print('YOU ARE IN THE PUT REQUEST ON DJANGO FOR DECLINE FRIEND REQUESTS')
    user_email = request.user.email
    user = getUser(user_email)
    friend_email = request.data['friend_email']
    friend = getUser(friend_email)
    friend_request = FriendRequest.objects.get(sender = friend, receiver = user, is_active = True)
    if friend_request:
        friend_request.is_active = False
        friend_request.save()
        try:
            return JsonResponse({'success':True, 'reason': 'friend request is now inactive'})
        except:
            return JsonResponse({'success': False, 'reason': 'something went wrong'})
    else:
        return JsonResponse({'success': False, 'reason': "you don't have a request from this friend"})

def create_card(game, owner):
    try:
        # global cardCount
        # its ok for cards to be global because its random each time a game is started, and the cardCount will be tied to each game
        global cards
        card_count = game.card_count
        # if cards doesnt have enough cards in it to draw another card:
        if len(cards)<= card_count:
            print('NOT ENOUGH CARDS, GENERATING MORE')
            getCards()
        game_card = Game_Card(phrase=cards[card_count], game = game, face_up = False, votes = 0, owner = owner, round_selected=0, is_active = True)
        # need to do something to not allow duplicate phrases
        game_card.full_clean()
        game_card.save()
        print('GAME CARD = :', game_card)
        game.card_count+=1
        game.save()
        return game_card 
    except Exception as e:
        print(str(e))
        return JsonResponse({'success': False, 'reason': str(e)})


@api_view(['PUT'])
@login_required
def draw_card(request):
    print('IN DRAW CARD ON DJANGO')
    user_email = request.user.email
    user = getUser(user_email)
    # game_user= Game_User.objects.get(player = user)
    # still running into issue of multiple game users
    game_user_objects = Game_User.objects.filter(player = user)
    owner = game_user_objects[len(game_user_objects)-1]
    print('DRAW CARD OWNER IS', owner)
    game_code = request.data['game_code']
    game = Game.objects.get(code = game_code)
    print('draw card game is', game, 'draw card game round is', game.round)
    try:
        new_card = create_card(game, owner)
        return JsonResponse({'success':True, 'drawn_card':model_to_dict(new_card)})
    except Exception as e:
        return JsonResponse({'success': False, 'reason': str(e)})

@api_view(['POST'])
@login_required
def start_game(request):
    print('YOU ARE IN THE POST REQUEST ON DJANGO FOR START GAME')
    user_email = request.user.email
    user = getUser(user_email)
    code = str(random.randint(10001,999999))
    try:
        game = Game(code = code)
        game.full_clean
        game.save()
        game_code = game.code
        game_user = Game_User(game = game, player = user)
        game_user.full_clean
        game_user.save()
        # print('IN START GAME -- GAME CODE IS', game_code)
        getCards()
        user_cards = []
        while len(user_cards) < 6:
            card=create_card(game, game_user)
            user_cards.append(model_to_dict(card))
        # print('USER CARDS ARE', user_cards, 'len user cards', len(user_cards))
        return JsonResponse({'success':True, 'game': model_to_dict(game), 'user_cards': user_cards, 'game_user':model_to_dict(game_user)})
    except Exception as e:
        return JsonResponse({'success': False, 'reason': str(e)})
    
    # need to account for if they're showing up as in a different game
    # when client goes back to lobby need to set them as inactive game user. Or delete game user??

@api_view(['POST'])
@login_required
def join_game(request):
    game_code= request.data['game_code']
    user_email = request.user.email
    user = getUser(user_email)
    game = Game.objects.get(code = game_code)
    if (game):
        try:
            game_user = Game_User(game = game, player = user)
            game_user.full_clean
            game_user.save()
            print('JOIN GAME USER IS!!!! ', game_user)
            getCards()
            user_cards = []
            while len(user_cards) < 6:
                card=create_card(game, game_user)
                user_cards.append(model_to_dict(card))
            return JsonResponse({'success':'True','user_cards': user_cards, 'game': model_to_dict(game)})
        except Exception as e:
            return JsonResponse({'success': False, 'reason': str(e)})
    else:
        return JsonResponse({'success': False, 'reason': 'there is nobody playing on that game code, please try again or start a game'})
    
    

@api_view(['PUT'])
@login_required
def selected_card(request):
    print('YOU ARE IN THE PUT REQUEST ON DJANGO FOR SELECTED CARD')
    round = request.data['round']
    card_id= request.data['id']
    # print('SELECTED CARD_ID', card_id, 'TYPE', type(card_id), 'CARD ROUND', round)
    card = Game_Card.objects.get(id=card_id)
    print('CARD SELECTED', card)
    try:
        card.round_selected = round
        card.save()
        # print('round selected', card.round_selected)
        return JsonResponse({'success':True, 'action': 'card round selected updated'})
    except Exception as e:
        return JsonResponse({'success': False, 'reason': f'something went wrong {str(e)}'})

# @api_view(['GET'])
# @login_required    
# def view_selected_cards(request):
#     print('YOU ARE IN THE VIEW SELECTED CARDS')
#     user_email = request.user.email
#     user = getUser(user_email)
#     # game_user= Game_User.objects.get(player = user)
#     game_user = Game_User.objects.filter(player = user)
#     game_1 = game_user[len(game_user)-1].game
#     round = game_1.round
#     print('VIEW SELECTED CARDS GAME', game_1, 'SELECTED CARDS ROUND', round)
#     selected_cards_objects= Game_Card.objects.filter(round_selected=round, game = game_1)
#     print('SELECTED CARD OBJECTS LINE 453', selected_cards_objects)
#     if selected_cards_objects:
#         try:
#             selected_cards=[]
#             for card in selected_cards_objects:
#                 if model_to_dict(card) not in selected_cards:
#                     selected_cards.append(model_to_dict(card))
#             return JsonResponse({'success':True, 'selected_cards': selected_cards})
#         except Exception as e:
#             return JsonResponse({'success': False, 'reason': f'something went wrong {str(e)}'})
#     else: 
#         return JsonResponse({'success':False, 'reason': 'no selected cards'})

@api_view(['POST'])
@login_required
def vote(request):
    card_id= request.data['id']
    round= request.data['round']
    print('VOTED FOR CARD_ID', card_id, 'round', round)
    user_email = request.user.email
    user = getUser(user_email)
    # game_user= Game_User.objects.get(player = user)
    # still running into issue of multiple game users
    game_user = Game_User.objects.filter(player = user)
    game_user_1 = game_user[len(game_user)-1]
    card = Game_Card.objects.get(id=card_id)
    # print('CARD VOTED FOR', card)
    try:
        card.votes+=1
        card.save()
        print('CARD VOTES', card.votes)
        game_user_1.completed_vote_on_round= round
        print('PLAYER COMPLETED VOTE ON ROUND', game_user_1.completed_vote_on_round)
        return JsonResponse({'success':True, 'reason': 'card has been voted on and players vote counted'})
    except Exception as e:
        return JsonResponse({'success': False, 'reason': f'something went wrong {str(e)}'})

# @api_view(['PUT'])
# # doing a put so I can pass in the round
# @login_required    
# def view_votes(request):
#     print('YOU ARE IN THE VIEW VOTES')
#     round = request.data['round']
#     game_code = request.data['game_code']
#     print('GAME CODE LINE 479', game_code)
#     game = Game.objects.get(code = game_code)
#     print('VIEW VOTE GAME', game)
#     # cards that were selected that round
#     # don't think I need to do this b/c can just grab the votes from the front end since I'm sending in the object cards
#     # selected_cards_objects= Game_Card.objects.filter(round_selected=round, game = game)
#     players_that_voted_objects = Game_User.objects.filter(completed_vote_on_round = round, game= game)
#     print('PLAYERS THAT VOTED', players_that_voted_objects)
#     if players_that_voted_objects:
#         try:
#             players_that_voted=[]
#             for game_user in players_that_voted_objects:
#                 user = game_user.player
#                 if user.email not in players_that_voted:
#                     players_that_voted.append(user.email)
#             return JsonResponse({'success':True, 'players_that_voted': players_that_voted})
#         except Exception as e:
#             return JsonResponse({'success': False, 'reason': f'something went wrong {str(e)}'})
#     else: 
#         return JsonResponse({'success':False, 'reason': 'nobody has voted yet'})

# @api_view(['GET'])
# @login_required    
# def players(request):
#     # print('YOU ARE IN THE PLAYERS')
#     user_email = request.user.email
#     user = getUser(user_email)
#     # game_user= Game_User.objects.get(player = user)
#     game_user = Game_User.objects.filter(player = user)
#     game = game_user[len(game_user)-1].game    
#     all_game_users= Game_User.objects.filter(game = game)
#     print('ALL GAME USERS', all_game_users)
#     if all_game_users:
#         try:
#             players=[]
#             game_user_array=[]
#             for game_user in all_game_users:
#                 user = game_user.player
#                 if user.email not in players:
#                     players.append([user.email, game_user.player_points])
#                 if model_to_dict(game_user) not in game_user_array:
#                     game_user_array.append(model_to_dict(game_user))
#             print('GAME USER ARRAY LINE 540', game_user_array)
#             return JsonResponse({'success':True, 'players': players, 'game_user_array': game_user_array})
#         except Exception as e:
#             return JsonResponse({'success': False, 'reason': f'something went wrong {str(e)}'})
#     else: 
#         return JsonResponse({'success':False, 'reason': 'no players in this game'})

@api_view(['PUT'])
@login_required
def leave_game(request):
    print('YOU ARE IN THE PUT REQUEST ON DJANGO FOR LEAVE GAME')
    # print('request', request)
    user_email = request.user.email
    user = getUser(user_email)
    print('USER =', user)
    game_user_objects= Game_User.objects.filter(player = user)
    # game_user= game_user_objects[len(game_user_objects)-1]
    # print('GAME USER = ', game_user)
    try:
        game_user_objects.delete()
        # this will also delete all game_cards that belonged to that user
        print('GAME USERS SHOULD BE DELETED', game_user_objects)
        return JsonResponse({'success':True, 'action': 'left game and game_user deleted'})
    except Exception as e:
        return JsonResponse({'success': False, 'reason': f'something went wrong {str(e)}'})

@api_view(['POST'])
def points(request):
    user_email = request.user.email
    user = getUser(user_email)
    print('IN POINTS ON DJANGO')
    print('REQUEST.DATA in points', request.data)
    # print(dir(request))
    winningCard_id = request.data["winningCard"]
    winningCard = Game_Card.objects.get(id = winningCard_id)
    print('WINNING CARD ID', winningCard_id)
    print('winning card', winningCard)
    # this is the actual model, not just the id:
    game_user = winningCard.owner 
    print('user of winning card', game_user, 'TYPE', type(game_user))
    try:
        if (game_user.player == user):
            game_user.player_points+=1
            game_user.save()
            print('GAME USER SHOULD NOW HAVE ANOTHER POINT', game_user.player_points)
        user = game_user.player
        user_email = user.email
        return JsonResponse({'success':True, 'winningCardOwner': user.email})
    except Exception as e:
        return JsonResponse({'success': False, 'reason': f'something went wrong {str(e)}'})

@api_view(['PUT'])
# put request so could have body
def round(request):
    game_code = request.data['code']
    print('IN GET ROUND code is ', game_code)
    try:
        game = Game.objects.get(code = game_code)
        game_round = game.round
        return JsonResponse({'success':True, 'round': game_round})
    except Exception as e:
        return JsonResponse({'success': False, 'reason': f'something went wrong {str(e)}'})

@api_view(['POST'])
# put request so could have body
def reset_round(request):
    game_code = request.data['code']
    game = Game.objects.get(code = game_code)
    user_email = request.user.email
    winningcard_owner_id= request.data['owner_id']
    print('OWNER ID LINE 612', winningcard_owner_id)
    user = getUser(user_email)
    # game_user= Game_User.objects.get(player = user)
    # still running into issue of multiple game users
    game_user_objects = Game_User.objects.filter(player = user)
    owner = game_user_objects[len(game_user_objects)-1]
    print('IN RESET ROUND code is ', game_code, 'OWNER ID is', owner.id)
    try:
        if (winningcard_owner_id == owner.id):
            game.round+=1
            game.save()
            print('GAME SHOULD BE ONE ROUND HIGHER', game.round)
            return JsonResponse({'success':True, 'action': 'round reset'})
        # new_card = create_card(game,owner)
        # drawn_card = model_to_dict(new_card)
        # return JsonResponse({'success':True, 'action': 'round reset', 'drawn_card': drawn_card})
        else:
            return JsonResponse({'success':True, 'action': 'round reset'})
    except Exception as e:
        return JsonResponse({'success': False, 'reason': f'something went wrong {str(e)}'})

@api_view(['GET'])
@login_required    
def game_info(request):
    print('YOU ARE IN THE GET GAME INFO')
    user_email = request.user.email
    user = getUser(user_email)
    game_user = Game_User.objects.filter(player = user)
    game = game_user[len(game_user)-1].game
    all_game_users= Game_User.objects.filter(game = game)
    print('ALL GAME USERS', all_game_users)
    round = game.round
    print('VIEW SELECTED CARDS GAME', game, 'SELECTED CARDS ROUND', round)
    selected_cards_objects= Game_Card.objects.filter(round_selected=round, game = game)
    print('SELECTED CARD OBJECTS LINE 654', selected_cards_objects)
    selected_cards = []
    try:
        if selected_cards_objects:
            for card in selected_cards_objects:
                if model_to_dict(card) not in selected_cards:
                    selected_cards.append(model_to_dict(card))
        players=[]
        game_user_array=[]
        for game_user in all_game_users:
            user = game_user.player
            if user.email not in players:
                players.append([user.email, game_user.player_points])
            if model_to_dict(game_user) not in game_user_array:
                game_user_array.append(model_to_dict(game_user))
        print('GAME USER ARRAY LINE 669', game_user_array)            
        return JsonResponse({'success':True, 'selected_cards': selected_cards, 'players': players, 'game_user_array': game_user_array, 'game': model_to_dict(game)})
    except Exception as e:
        return JsonResponse({'success': False, 'reason': f'something went wrong {str(e)}'})
    # else: 
    #     return JsonResponse({'success':False, 'reason': 'no selected cards'})

# I just added 'get players' and 'get game users' into this function, I need to change around my function about figuring out who has voted. Also the user who JOINED the game didnt have "leave game" option in navbar.



# source ~/VEnvirons/WhatTheMeme/bin/activate
# http://127.0.0.1:8000/