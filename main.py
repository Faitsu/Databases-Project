import datetime
import os

import hashlib  # for salting to work

# Import Flask Library
from flask import Flask, render_template, request, session, url_for, redirect, flash, send_from_directory
from werkzeug.utils import secure_filename
import pymysql.cursors  # for interacting with database

# Path for uploads folder

UPLOAD_FOLDER = '/Users/erica/Databases-Project/uploads'

ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg'])

# Salt defined
SALT = 'moira11QYC22erica33'

# Initialize the app from Flask
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Configure MySQL
conn = pymysql.connect(host='localhost',
                       port = 3308,
                       user='root',
                       password='',
                       db='FinstagramDB',
                       charset='utf8mb4',
                       cursorclass=pymysql.cursors.DictCursor)


# Define a route to hello function
@app.route('/')
def hello():
    return render_template('index.html')


# Define route for login
@app.route('/login')
def login():
    return render_template('login.html')


# Define route for register
@app.route('/register')
def register():
    return render_template('register.html')


# Authenticates the login
@app.route('/loginAuth', methods=['GET', 'POST'])
def loginAuth():
    # grabs information from the forms
    username = request.form['username']
    password = request.form['password'] + SALT

    hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()

    # cursor used to send queries
    cursor = conn.cursor()
    # executes query
    query = 'SELECT * FROM Person WHERE username = %s and password = %s'
    cursor.execute(query, (username, hashed_password))
    # stores the results in a variable
    data = cursor.fetchone()
    # use fetchall() if you are expecting more than 1 data row
    cursor.close()
    error = None
    if (data):
        # creates a session for the the user
        # session is a built in
        session['username'] = data['username']
        return redirect(url_for('home'))
    else:
        # returns an error message to the html page
        error = 'Invalid login or username'
        return render_template('login.html', error=error)


# Authenticates the register
@app.route('/registerAuth', methods=['GET', 'POST'])
def registerAuth():
    # grabs information from the forms
    username = request.form['username']
    password = request.form['password'] + SALT
    firstName = request.form['firstName']
    lastName = request.form['lastName']
    email = request.form['email']

    # cursor used to send queries
    cursor = conn.cursor()
    # executes query
    query = 'SELECT * FROM Person WHERE username = %s'
    cursor.execute(query, (username))
    # stores the results in a variable
    data = cursor.fetchone()
    # use fetchall() if you are expecting more than 1 data row
    error = None
    if (data):
        # If the previous query returns data, then user exists
        error = "User already exists"
        return render_template('register.html', error=error)
    else:
        hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()
        ins = 'INSERT INTO Person VALUES(%s, %s, %s, %s, %s)'
        cursor.execute(ins, (username, hashed_password, firstName, lastName, email))
        conn.commit()
        cursor.close()
        return render_template('index.html')


# Define a route to home
@app.route('/home')
def home(error=''):
    username = session['username']
    cursor = conn.cursor()

    # query for posted photos (user posted)
    query = 'SELECT pID, poster, filePath, caption, allFollowers, postingDate FROM Photo WHERE poster = %s ORDER BY postingDate DESC'
    cursor.execute(query, (username))
    data = cursor.fetchall()
    conn.commit()

    # query for groups that user can share photos with (user = groupCreator)
    query = 'SELECT groupName FROM FriendGroup WHERE groupCreator = %s'
    cursor.execute(query, (username))
    groupsToShare = cursor.fetchall()
    conn.commit()

    # query for photos user can view
    query = 'SELECT pID, filePath, caption, postingDate, poster FROM Follow JOIN Photo ON (Photo.poster = Follow.followee) WHERE follower = %s AND followStatus = 1 UNION SELECT pID, filePath, caption, postingDate, poster FROM BelongTo NATURAL JOIN SharedWith NATURAL JOIN Photo WHERE username = %s UNION SELECT pID, filePath, caption, postingDate, poster FROM Photo WHERE poster = %s AND allFollowers = 1 ORDER BY pID DESC '
    cursor.execute(query, (username, username,username))
    sharedPhotos = cursor.fetchall()
    conn.commit()

    cursor.close()

    if (error == ''):  # no errors
        return render_template('home.html', username=username, sharedPhotos=sharedPhotos, groups=groupsToShare,
                               posts=data)
    else:
        return render_template('home.html', username=username, sharedPhotos=sharedPhotos, groups=groupsToShare,
                               posts=data, error=error)


# Retrieve image from uploads folder (static)
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory("uploads", filename)


# To check if filename is of appropriate type
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Share photo with groups
def share_with_groups(pID, filePath, caption, poster, groupNames):
    cursor = conn.cursor()

    for group in groupNames:
        # inserting to sharedWith
        ins2 = 'INSERT INTO SharedWith (pID, groupName, groupCreator) VALUES(%s, %s, %s)'
        cursor.execute(ins2, (pID, group, poster))
        conn.commit()

    cursor.close()
    return redirect(url_for('home'))


# Posting & sharing photos
@app.route('/post', methods=['GET', 'POST'])
def post():
    if (request.method == 'POST'):
        poster = session['username']
        caption = request.form['caption']

        # error if nothing is chosen for who to share photo with
        try:
            allFollowers_temp = request.form['allFollowers_temp']
        except:
            return home('INVALID: You must pick who to share photo with!')

        # change flag depending on who the photo is shared with
        if (allFollowers_temp == 'followers'):
            allFollowers = 1  # all followers
        else:
            allFollowers = 0  # members of friend group

        postingDate = datetime.datetime.now()
        groupNames = request.form.getlist('groups')

        # post a photo
        cursor = conn.cursor()
        ins = 'INSERT INTO Photo (postingDate, allFollowers, caption, poster) VALUES(%s, %s, %s, %s)'
        cursor.execute(ins, (postingDate, allFollowers, caption, poster))
        conn.commit()

        # get the pID of photo just posted
        query = 'SELECT LAST_INSERT_ID()'
        cursor.execute(query)
        conn.commit()
        pID_temp = cursor.fetchone()
        pID = pID_temp['LAST_INSERT_ID()']

        # check file
        if 'filePath_img' not in request.files:
            flash('No file part')
            return redirect(url_for('home'))

        filePath = request.files['filePath_img']
        # if user does not select file, browser also
        # submit an empty part without filename
        if filePath.filename == '':
            flash('No selected file')
            return redirect(url_for('home'))
        if filePath and allowed_file(filePath.filename):
            filename = secure_filename(filePath.filename)

            # update filename to be pID
            nameSplit = filename.split('.')
            nameSplit[0] = str(pID)
            filename_update = '.'.join(nameSplit)

            filePath.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_update))
            filePath = filename_update

        # update filePath in Photo table
        update = 'UPDATE Photo SET filePath=%s WHERE pID=%s'
        cursor.execute(update, (filePath, pID))
        conn.commit()

        cursor.close()

        # share with group if flag indicates so
        if (allFollowers == 0):
            share_with_groups(pID, filePath, caption, poster, groupNames)

    return redirect(url_for('home'))


# Define route for manage_group
@app.route('/manageGroups')
def group(error=''):
    username = session['username']
    cursor = conn.cursor()

    query = 'SELECT username FROM Person WHERE username != %s'
    cursor.execute(query, (username))
    users = cursor.fetchall()
    conn.commit()

    query1 = 'SELECT groupName, description FROM FriendGroup WHERE groupCreator = %s'
    cursor.execute(query1, (username))
    groups = cursor.fetchall()
    conn.commit()

    query2 = 'SELECT groupName, groupCreator FROM BelongTo WHERE username = %s'
    cursor.execute(query2, (username))
    groups1 = cursor.fetchall()
    conn.commit()

    cursor.close()

    if (error == ''):  # no errors
        return render_template('manage_group.html', users=users, groups=groups, belongsToGroup=groups1)
    else:
        return render_template('manage_group.html', users=users, groups=groups, belongsToGroup=groups1, error=error)


# Create a group
@app.route('/makeGroup', methods=['GET', 'POST'])
def makeGroup():
    username = session['username']
    groupName = request.form['groupName']
    description = request.form['description']

    chosenMem = request.form.getlist('chosenMem')

    cursor = conn.cursor()
    query = 'SELECT * FROM FriendGroup WHERE groupName = %s AND groupCreator = %s'
    cursor.execute(query, (groupName, username))
    data = cursor.fetchone()

    error = None
    if (data):
        error = 'INVALID: You have already created a group with this name!'
        cursor.close()
        return group(error)
    else:
        ins = 'INSERT INTO FriendGroup (groupName, groupCreator, description) VALUES(%s, %s, %s)'
        cursor.execute(ins, (groupName, username, description))
        conn.commit()

        ins = 'INSERT INTO BelongTo (username, groupName, groupCreator) VALUES(%s, %s, %s)'
        cursor.execute(ins, (username, groupName, username))
        conn.commit()

        for user in chosenMem:
            ins = 'INSERT INTO BelongTo (username, groupName, groupCreator) VALUES(%s, %s, %s)'
            cursor.execute(ins, (user, groupName, username))
            conn.commit()

        cursor.close()
        # return redirect(url_for('home'))
        return redirect(url_for('group'))


# Define route for tag_photo
@app.route('/tag')
def tag(error=''):
    username = session['username']
    cursor = conn.cursor()

    # query for photos the user posted
    query = 'SELECT pID, poster, filePath, caption, allFollowers, postingDate FROM Photo WHERE poster = %s ORDER BY postingDate DESC'
    cursor.execute(query, (username))
    userPosts = cursor.fetchall()
    conn.commit()

    cursor.close()

    if (error == ''):
        return render_template('tag_photo.html', photos=userPosts)
    else:
        return render_template('tag_photo.html', photos=userPosts, error=error)


# Tag a username to a photo
@app.route('/tagPhoto', methods=['GET', 'POST'])
def tagPhoto():
    username = session['username']

    # error if nothing is chosen for who to share photo with
    try:
        photoChosen = request.form['photoChosen']
    except:
        return tag('INVALID: You must pick a photo to tag user in!')

    tagUser = request.form['tagUser']

    # check if entered username exists
    cursor = conn.cursor()
    query = 'SELECT * FROM Person WHERE username = %s'
    cursor.execute(query, (tagUser))
    userFound = cursor.fetchone()

    if (userFound):
        tagUser = userFound['username']
        visible = False

        # check if user is already tagged in photo
        query = 'SELECT pID, username FROM Tag WHERE pID = %s AND username = %s'
        cursor.execute(query, (photoChosen, tagUser))
        tagUserFound = cursor.fetchone()

        # found tagUser + photoID in Tag table
        if (tagUserFound):
            cursor.close()
            return tag('INVALID: Tag has already been proposed before!')

        # user is self-tagging
        if (tagUser == username):
            tagFlag = 1  # true (automatically accepted tag)
            visible = True
        else:
            # check if photo is visible to tagUser
            query = 'SELECT pID FROM Follow JOIN Photo ON (Photo.poster = Follow.followee) WHERE follower = %s AND followStatus = 1 UNION SELECT pID FROM BelongTo NATURAL JOIN SharedWith NATURAL JOIN Photo WHERE username = %s ORDER BY pID DESC'
            cursor.execute(query, (tagUser, tagUser))
            sharedPID = cursor.fetchall()
            conn.commit()

            for pID in sharedPID:
                if (str(pID['pID']) == photoChosen):
                    tagFlag = 0  # false (not yet accepted tag)
                    visible = True

        if (visible):
            # add tag to Tag table
            ins = 'INSERT INTO Tag (pID, username, tagStatus) VALUES(%s, %s, %s)'
            cursor.execute(ins, (photoChosen, tagUser, tagFlag))
            conn.commit()

            cursor.close
            return redirect(url_for('tag'))
        else:
            cursor.close
            return tag('INVALID: Cannot propose this tag!')

    else:
        cursor.close
        return tag('INVALID: Username you entered does not exist!')


# Define route for tag_photo
@app.route('/tagPending')
def tagPending(error=''):
    username = session['username']
    cursor = conn.cursor()

    # query for pending photos the user is tagged in
    query = 'SELECT pID, filePath, caption, postingDate FROM Photo NATURAL JOIN Tag WHERE tagStatus=%s AND username=%s ORDER BY postingDate DESC'
    cursor.execute(query, (0, username))
    pendingTags = cursor.fetchall()
    conn.commit()

    # query for photos user is tagged in & user has already approved
    query = 'SELECT pID, filePath, caption, poster, postingDate FROM Photo NATURAL JOIN Tag WHERE username = %s AND tagStatus = %s ORDER BY pID DESC'
    cursor.execute(query, (username, 1))
    taggedPhotos = cursor.fetchall()
    conn.commit()

    cursor.close()

    if (error == ''):
        return render_template('tag_pendings.html', approvedTags=taggedPhotos, tags=pendingTags)
    else:
        return render_template('tag_pendings.html', approvedTags=taggedPhotos, tags=pendingTags, error=error)


# Check if pID is in list (used to check if user selected approve & decline)
def isInList(pID, list):
    for i in list:
        if (i == pID):
            return True
    return False


# Manage pending tags
@app.route('/approveTag', methods=['GET', 'POST'])
def tagDecision():
    username = session['username']
    approved = request.form.getlist('decisionY')
    declined = request.form.getlist('decisionN')

    decisionNY = False

    cursor = conn.cursor()

    for pID in approved:
        # if pID is only in approved
        if (isInList(pID, declined) == False):
            # update the tagStatus = 1 (accepted)
            update = 'UPDATE Tag SET tagStatus=%s WHERE pID=%s AND username=%s'
            cursor.execute(update, (1, pID, username))
            conn.commit()
        else:
            decisionNY = True
    for pID in declined:
        # if pID is only in declined
        if (isInList(pID, approved) == False):
            # delete tag from Tag table
            delete = 'DELETE FROM Tag WHERE pID=%s AND username=%s'
            cursor.execute(delete, (pID, username))
            conn.commit()
        else:
            decisionNY = True
    cursor.close()
    if(decisionNY):
        return tagPending('INVALID: Cannot accept and decline tag(s)!')
    return redirect('/tagPending')



# Tab for looking at more information about the picture
@app.route('/photoInfo/<string:pID>')
def photoinfo(pID, error = ''):
    cursor = conn.cursor()
    username = session['username']

    # query for selecting what Photo is shown
    query = 'SELECT pID, filePath, caption, postingDate, poster, firstName, lastName FROM photo JOIN person ON (photo.poster = person.username) WHERE pID = %s'
    cursor.execute(query, pID)
    photo = cursor.fetchall()
    conn.commit()

    #query for looking for who was tagged in the photo
    query = 'SELECT username FROM Tag WHERE pID = %s AND tagStatus = 1'
    cursor.execute(query, pID)
    tag = cursor.fetchall()
    conn.commit()

    #query for looking for who reacted the photo
    query = 'SELECT username, reactionTime, comment, emoji FROM reactto WHERE pID = %s'
    cursor.execute(query, pID)
    reacts = cursor.fetchall()
    conn.commit()

    cursor.close()

    if (error == ''):
        return render_template('photoinfo.html',username = username, Photos = photo, tag = tag, reacts = reacts)
    else:
        return render_template('photoinfo.html', username = username, Photos = photo , tag = tag, reacts = reacts, error=error)


#code for adding reactions and comments to a photo
@app.route('/photoreactorcomment/<string:pID>', methods=['GET', 'POST'])
def photoreactorcomment(pID):
    username = session['username']
    comment = request.form['comment']
    emoji = request.form['emoji']

    reactionTime = datetime.datetime.now()

    cursor = conn.cursor()
    query = 'SELECT * FROM reactto WHERE username = %s AND pID = %s'
    cursor.execute(query,(username, pID))
    data = cursor.fetchone()

    error = None
    if (data):
        error = 'INVALID: You have already commented and reacted to this photo!'
        cursor.close()
        return photoinfo(pID,error)
    else:
        ins = 'INSERT INTO reactto (username,pID,reactionTime, comment,emoji) VALUES(%s, %s, %s,%s,%s)'
        cursor.execute(ins, (username, pID, reactionTime, comment,emoji))
        conn.commit()


        cursor.close()
        return redirect(url_for('photoinfo', pID = pID))


# Define route to follow a user
@app.route('/newFollow')
def newFollow(error=''):
    if (error == ''):
        return render_template('follow_user.html')
    else:
        return render_template('follow_user.html', error=error)

# Inputs request of current user to follow another user
@app.route('/follow', methods=['GET', 'POST'])
def followUser():
    userFollowing = session['username']
    userToFollow = request.form['followName']
    cursor = conn.cursor()

    # check if they're trying to follow themselves
    if (userToFollow == userFollowing):
        cursor.close()
        return newFollow('INVALID: You cannot follow yourself!')

    # check if entered username exists
    query = 'SELECT * FROM Person WHERE username = %s'
    cursor.execute(query, (userToFollow))
    userFound = cursor.fetchone()

    if (userFound):

        # check if they already requested to follow the user
        query = 'SELECT followee FROM follow WHERE follower = %s'
        cursor.execute(query, userFollowing)
        followUserFound = cursor.fetchone()

        if (followUserFound):
            cursor.close()
            return newFollow('INVALID: You have already requested to follow this user!')

        userToFollow = userFound['username']
        query1 = 'INSERT INTO follow (follower, followee, followStatus) VALUES (%s, %s, 0)'
        cursor.execute(query1, (userFollowing, userToFollow))
        conn.commit()

    else:
        cursor.close
        return newFollow('INVALID: Username you entered does not exist!')

    return redirect(url_for('home'))

# Define route to approve/reject follow requests
@app.route('/viewRequests')
def viewRequests(error=''):

    username = session['username']
    cursor = conn.cursor()

    # Query to find the users requesting to follow the current user.
    query = 'SELECT follower FROM follow WHERE followee = %s AND followStatus = 0'
    cursor.execute(query, username)
    requestedFollowers = cursor.fetchall()
    conn.commit()

    cursor.close()

    if (error == ''):
        return render_template('manage_follows.html', requestedFollowers=requestedFollowers)
    else:
        return render_template('manage_follows.html', requestedFollowers=requestedFollowers, error=error)

# Manages list of requests others have made to follow the current user
@app.route('/manageFollows', methods=['GET', 'POST'])
def manageFollows():
    followeeUser = session['username']
    requestedFollowers = request.form.getlist('requestedFollowers')
    followAction = request.form['followAction']

    cursor = conn.cursor()
    for followerUser in requestedFollowers:
        query = 'DELETE FROM follow WHERE followee = %s AND follower = %s'
        cursor.execute(query, (followeeUser, followerUser))
        if (followAction == 'Accept'):
            query = 'INSERT INTO follow (follower, followee, followStatus) VALUES (%s, %s, 1)'
            cursor.execute(query, (followerUser, followeeUser))

    conn.commit()
    cursor.close()

    return redirect(url_for('home'))

# Define a route to search by poster
@app.route('/searchPoster')
def searchPoster(error=''):
    if (error == ''):  # no errors
        return render_template('select_blogger.html')
    else:
        return render_template('select_blogger.html', error=error)

# Search for photos visible to user and posted by a particular user
@app.route('/searchByPoster', methods=['GET', 'POST'])
def searchByPoster(error=''):
    username = session['username']
    bloggerSearch = request.form['bloggerName']
    cursor = conn.cursor()

    # check if entered username exists
    query = 'SELECT * FROM Person WHERE username = %s'
    cursor.execute(query, (bloggerSearch))
    userFound = cursor.fetchone()

    if (userFound):
        query = 'SELECT pID, filePath, caption, postingDate, poster FROM Follow JOIN Photo ON (Photo.poster = Follow.followee) WHERE follower = %s AND poster = %s UNION SELECT pID, filePath, caption, postingDate, poster FROM BelongTo NATURAL JOIN SharedWith NATURAL JOIN Photo WHERE username = %s AND poster = %s UNION SELECT pID, filePath, caption, postingDate, poster FROM Photo WHERE poster = %s AND poster = %s AND allFollowers = 1 ORDER BY pID DESC'
        cursor.execute(query, (username, bloggerSearch, username, bloggerSearch, username, bloggerSearch))
        bloggerPosts = cursor.fetchall()
        conn.commit()

    else:
        cursor.close
        return searchPoster('INVALID: Username you entered does not exist!')

    if (error == ''):
        return render_template('show_posts.html', bloggerSearch=bloggerSearch, bloggerPosts=bloggerPosts)
    else:
        return render_template('show_posts.html', bloggerSearch=bloggerSearch, bloggerPosts=bloggerPosts, error=error)

# Define a route to search by tag
@app.route('/searchTag')
def searchTag(error=''):
    if (error == ''):  # no errors
        return render_template('search_tag.html')
    else:
        return render_template('search_tag.html', error=error)

# Search for photos visible to user and that tag a particular person
@app.route('/searchByTag', methods=['GET', 'POST'])
def searchByTag(error=''):
    username = session['username']
    tagSearch = request.form['taggedUser']
    cursor = conn.cursor()

    # check if entered username exists
    query = 'SELECT * FROM Person WHERE username = %s'
    cursor.execute(query, (tagSearch))
    userFound = cursor.fetchone()

    if (userFound):
        query = 'CREATE VIEW viewablePhotos AS SELECT pID, filePath, caption, postingDate, poster FROM Follow JOIN Photo ON (Photo.poster = Follow.followee) WHERE follower = %s UNION SELECT pID, filePath, caption, postingDate, poster FROM BelongTo NATURAL JOIN SharedWith NATURAL JOIN Photo WHERE username = %s ORDER BY pID DESC'
        cursor.execute(query, (username, username))
        conn.commit()

        query1 = 'SELECT pID, filePath, caption, postingDate, poster FROM viewablePhotos WHERE pID IN (SELECT pID FROM Tag WHERE username = %s AND tagStatus = %s)'
        cursor.execute(query1, (tagSearch, 1))
        taggedPosts = cursor.fetchall()
        conn.commit()

        query2 = 'DROP VIEW viewablePhotos'
        cursor.execute(query2)
        conn.commit()

    else:
        cursor.close
        return searchTag('INVALID: Username you entered does not exist!')

    if (error == ''):
        return render_template('show_tags.html', tagSearch=tagSearch, taggedPosts=taggedPosts)
    else:
        return render_template('show_tags.html', tagSearch=tagSearch, taggedPosts=taggedPosts, error=error)

# Define route for Unfollow: a page for unfollowing people
@app.route('/unfollow')
def unfollow(error=''):
    username = session['username']
    cursor = conn.cursor()

    # query for photos the user posted
    query = 'SELECT followee FROM follow WHERE follower = %s AND followStatus = 1'
    cursor.execute(query, (username))
    followinginfo = cursor.fetchall()
    conn.commit()

    cursor.close()

    if (error == ''):
        return render_template('unfollow.html', following=followinginfo)
    else:
        return render_template('unfollow.html', following=followinginfo, error=error)

# Code for unfollowing a certain person
@app.route('/unfollow_person', methods=['GET', 'POST'])
def unfollow_person():
    username = session['username']
    cursor = conn.cursor()
    # error if nothing is chosen for who to share photo with
    try:
        userChosen = request.form['userChosen']
    except:
        return tag('INVALID: You must pick a user to unfollow!')

    query = 'DELETE FROM follow WHERE follower = %s AND followee = %s'
    cursor.execute(query, (username,userChosen))
    conn.commit()

    query2 = 'DELETE FROM reactto WHERE username = %s AND pID IN(SELECT pID FROM photo WHERE poster = %s)'
    cursor.execute(query2, (username, userChosen))
    conn.commit()

    query3 = 'DELETE FROM tag WHERE username = %s AND pID IN(SELECT pID FROM photo WHERE poster = %s)'
    cursor.execute(query3, (username, userChosen))
    conn.commit()

    cursor.close()

    return redirect(url_for('unfollow'))

# Log out
@app.route('/logout')
def logout():
    session.pop('username')
    return redirect('/')


app.secret_key = 'some key that you will never guess'
# Run the app on localhost port 5000
# debug = True -> you don't have to restart flask
# for changes to go through, TURN OFF FOR PRODUCTION
if __name__ == "__main__":
    app.run('127.0.0.1', 5000, debug=True)
