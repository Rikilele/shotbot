import os
import math
import time
import random
import datetime

import redis
import dotenv

import anki_vector
from anki_vector.util import distance_mm, speed_mmps, degrees, radians
from anki_vector.objects import CustomObjectMarkers, CustomObjectTypes


#######################
# Database operations
#######################


# Converts a list into a comma-separated string
def list_to_str(arr):
    if len(arr) == 0:
        return ''
    return ','.join(str(e) for e in arr)


# Converts a comma-separated string into a list of integers
def str_to_list(s):
    if s == '':
        return []
    arr = s.split(',')
    return [int(e) for e in arr]


# Returns a redis connection
def open_db_connection():
    dotenv.load_dotenv()
    host = os.getenv('REDIS_HOST_NAME')
    password = os.getenv('REDIS_ACCESS_KEY')
    return redis.StrictRedis(host=host, port=6380, password=password, ssl=True)


# Create a new redis table and return the id and connection
def create_session_db(start_time):
    rdb = open_db_connection()
    session_id = str(abs(hash(start_time)))
    rdb.rpush('session_list', session_id)
    return session_id, rdb


# Checks if it is the person's first shot of the day
def is_first_shot(rdb, invitee_id):
    return not rdb.exists(invitee_id)


# Registers an invitee to the chill session
def register_invitee(rdb, robot, invitee_id, face):

    # Ask for their alcohol tolerance
    robot.say_text('Hello ' + face.name + '!')
    strength = ask_for_tolerance(robot)

    # Register user to db
    rdb.hset(invitee_id, 'name', face.name)
    rdb.hset(invitee_id, 'strength', strength)
    rdb.hset(invitee_id, 'shots_taken', '')

    robot.say_text('Registered ' + face.name + '!')


# Returns (strength [int], shots_taken [list]) of invitee
def retrieve_invitee_data(rdb, invitee_id):
    en = 'utf-8'
    strength = int(rdb.hget(invitee_id, 'strength').decode(en))
    shots_taken = str_to_list(rdb.hget(invitee_id, 'shots_taken').decode(en))
    return strength, shots_taken


# Updates shots_taken for invitee and stores to db
def update_invitee_data(rdb, invitee_id, shots_taken):
    shots_taken.append(datetime.datetime.now().second)
    rdb.hset(invitee_id, 'shots_taken', list_to_str(shots_taken))


#######################
# Movements
#######################


# Looks around for faces, and returns if he finds faces
def look_for_faces(robot):
    found_face = False
    while not found_face:
        dist = random.randint(0, 200)
        rot = random.randint(-90, 90)
        robot.behavior.turn_in_place(degrees(rot))
        time.sleep(1)
        robot.behavior.drive_straight(distance_mm(dist), speed_mmps(70))
        robot.behavior.set_head_angle(degrees(30))
        time.sleep(1)
        for trial in range(500):
            for _ in robot.world.visible_faces:
                found_face = True

        # Continue searching
        robot.behavior.set_head_angle(degrees(10))


# Looks up and returns the closest face
def identify_face(robot):
    robot.motors.set_head_motor(2)
    robot.anim.play_animation('anim_referencing_squint_01')
    robot.anim.play_animation('anim_eyecontact_squint_01')

    # Picks the closest face
    closest_face = None
    closest_dist = None
    for face in robot.world.visible_faces:
        robot_pos = robot.pose.position
        face_pos = face.pose.position
        dist_x = (robot_pos.x - face_pos.x) ** 2
        dist_y = (robot_pos.y - face_pos.y) ** 2
        dist_z = (robot_pos.z - face_pos.z) ** 2
        dist = (dist_x + dist_y + dist_z) ** 0.5
        if closest_dist is None or dist < closest_dist:
            closest_face = face
            closest_dist = dist

    if closest_face.name is None:
        return identify_face(robot)
    else:
        robot.anim.play_animation('anim_eyecontact_giggle_01_head_angle_40')
        return closest_face


# Asks for user input
def ask_for_tolerance(robot):
    strengths = ['Weak', 'Normal', 'Strong']
    robot.say_text(
        'How strong are you?' +
        'Please choose by pressing my button within 10 seconds!'
    )
    touch_count = 0
    robot.say_text(strengths[touch_count % 3])
    start_time = time.time()
    time_out = 10
    while (time.time() - start_time) < time_out:
        if robot.status.is_button_pressed:
            touch_count += 1
            robot.say_text(strengths[touch_count % 3])
            time.sleep(0.5)

    robot.say_text('You are ' + strengths[touch_count % 3])
    return touch_count % 3 + 1


def give_shot():
    with anki_vector.Robot(enable_custom_object_detection=True) as robot:
        robot.world.define_custom_cube(
            custom_object_type=CustomObjectTypes.CustomType00,
            marker=CustomObjectMarkers.Circles2,
            size_mm=20.0,
            marker_width_mm=50.0,
            marker_height_mm=50.0,
            is_unique=True
        )
        robot.motors.set_head_motor(0)
        robot.anim.play_animation('anim_referencing_squint_01')
        robot.anim.play_animation('anim_eyecontact_squint_01')
        robot.motors.set_lift_motor(0)

        for obj in robot.world.visible_custom_objects:
            new_pose = robot.pose.define_pose_relative_this(obj.pose)
            print(new_pose)
            x = new_pose.position.x
            y = new_pose.position.y
            z = new_pose.position.z
            ang = new_pose.rotation.angle_z
            a = x - (y / math.tan(ang.radians))

            speed = 80

            robot.behavior.drive_straight(distance_mm(x - 30),
                                          speed_mmps(speed))
            robot.behavior.turn_in_place(radians(math.pi / 3))
            robot.behavior.drive_straight(distance_mm(y - 30),
                                          speed_mmps(speed))
            robot.motors.set_lift_motor(2)
            robot.behavior.drive_straight(distance_mm(-y), speed_mmps(speed))

            # robot.behavior.drive_straight(distance_mm(y / math.sin(angle_z.radians)), speed_mmps(speed))
            # else:
            #     robot.behavior.turn_in_place(radians(math.pi / 2))
            #     robot.behavior.drive_straight(distance_mm(y - (x / math.tan(angle_z.radians))), speed_mmps(speed))
            #     robot.behavior.turn_in_place(radians(-angle_z.radians))
            #     robot.behavior.drive_straight(distance_mm(x / math.sin(angle_z.radians)), speed_mmps(speed))
            #     robot.motors.set_lift_motor(3)
            # robot.behavior.drive_straight(distance_mm(-x + a), speed_mmps(100))
            # robot.behavior.drive_straight(distance_mm(-y), speed_mmps(100))
            # robot.behavior.turn_in_place(radians(-angle_z.radians))

            # divisions = 5
            # for i in range(divisions):
            #     robot.behavior.drive_straight(distance_mm(x/5), speed_mmps(80))
            #     robot.behavior.turn_in_place(radians(math.pi / 2))
            #     robot.behavior.drive_straight(distance_mm(y/5), speed_mmps(80))
            #     robot.behavior.turn_in_place(radians(-math.pi / 2))


def hand_out_shot(robot, name):
    robot.say_text('Hey ' + name + ' let\'s take a shot!')
    give_shot()
    robot.say_text('Shot, shot, shot shot, shahshot, shot, shot shot, shahshot')


# Robot looks left and right
def look_around(robot):
    robot.behavior.turn_in_place(degrees(-30))
    time.sleep(3)
    robot.behavior.turn_in_place(degrees(30))


# Robot roams backwards
def roam_backwards(robot):
    robot.behavior.drive_straight(distance_mm(-100), speed_mmps(80))
    robot.behavior.turn_in_place(degrees(180))
    robot.behavior.drive_straight(distance_mm(-100), speed_mmps(80))
    robot.behavior.turn_in_place(degrees(180))
    time.sleep(2)


# Robot perform predetermined animations
def play_animations(robot):
    animation_names = robot.anim.anim_list
    anim = animation_names[random.randint(0, len(animation_names) - 1)]
    robot.anim.play_animation(anim)
    time.sleep(3)


# Robot uses arms to dance
def dance_with_arms(robot):
    for _ in range(0, 3):
        robot.motors.set_lift_motor(-5.0)
        time.sleep(0.5)
        robot.motors.set_lift_motor(5.0)
        time.sleep(0.5)
        robot.behavior.turn_in_place(degrees(90))
        robot.motors.set_lift_motor(-5.0)
        time.sleep(3)


# Randomly selects some actions to play for 10 minutes
def roam_around_freely(robot):
    time_end = time.time() + 60 * 1  # 10 minutes
    print('play animations')
    play_animations(robot)
    while time.time() < time_end:
        print('looking around')
        look_around(robot)
        print('roam backwards')
        roam_backwards(robot)
        print('dancing around')
        dance_with_arms(robot)
        time.sleep(10)
    print('play animations')
    play_animations(robot)


#######################
# Analysis
#######################


# Determines minimum time between shots
def min_shot_time(strength, shots_taken):
    slope = 1 * strength
    return slope * len(shots_taken)


# Determines whether to give shot depending on strength & last shot time
def person_needs_shot(strength, shots_taken, start_time):
    if len(shots_taken) == 0:
        return True
    min_time = min_shot_time(strength, shots_taken)
    time_now = datetime.datetime.now() - start_time
    time_now_sec = time_now.seconds
    time_delta = time_now_sec - shots_taken[-1]
    return time_delta > min_time


#######################
# Main
#######################


def main():
    print('set start time')
    start_time = datetime.datetime.now()

    print('establish db')
    session_id, rdb = create_session_db(start_time)

    print("open vector")
    # Open connection to Vector
    with anki_vector.Robot(
        enable_face_detection=True,
        enable_custom_object_detection=True
    ) as robot:

        # Event loop
        print('start event loop')
        robot.say_text('Please drink responsibly!')
        robot.behavior.drive_off_charger()
        while True:
            time_end = time.time() + 1  # for 5 minutes
            while time.time() < time_end:

                # Find one particular face
                print('looking for faces')
                look_for_faces(robot)

                print('gonna see face')
                face = identify_face(robot)
                invitee_id = session_id + '_' + str(face.face_id)

                # Register if not in db yet
                if is_first_shot(rdb, invitee_id):
                    print('registering new member')
                    register_invitee(rdb, robot, invitee_id, face)

                # Determine whether to give shot or not
                print('retrieving data')
                strength, shots_taken = retrieve_invitee_data(rdb, invitee_id)
                print('checking if shot is needed')
                if person_needs_shot(strength, shots_taken, start_time):
                    print('give shot')
                    hand_out_shot(robot, face.name)
                    update_invitee_data(rdb, invitee_id, shots_taken)

            # Provide slack
            print('roaming around freely')
            roam_around_freely(robot)


if __name__ == '__main__':
    main()
