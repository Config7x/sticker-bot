"""FSM states for the wizard, build-for-me flow and the admin panel."""
from aiogram.fsm.state import State, StatesGroup


class Wizard(StatesGroup):
    """Step-by-step pack creation (also used to add one sticker to a pack)."""

    choose_type = State()        # pack type (only static enabled in Phase 1)
    step_topic = State()         # step 1: topic
    step_sentence = State()      # step 2: sentence / text
    step_image = State()         # step 3: image
    step_style = State()         # step 4: style
    step_emoji = State()         # step 6: emoji (step 5 motion is Phase 2)
    step_name = State()          # step 7: pack title / cover
    manual_input = State()       # waiting for the user's own text/photo
    edit_input = State()         # waiting for edited suggestion text


class BuildForMe(StatesGroup):
    ask_topic = State()          # waiting for a topic text / pick
    preview = State()            # draft preview, per-sticker replace


class Admin(StatesGroup):
    add_channel = State()        # waiting for a channel @username / id
    add_bot = State()            # waiting for a bot username
    set_quota_packs = State()
    set_quota_stickers = State()
    edit_text = State()          # waiting for the new text body
    broadcast_text = State()     # waiting for broadcast message
    broadcast_confirm = State()  # waiting for confirm tap
    search_user = State()        # waiting for a user id / username query
