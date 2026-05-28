from datetime import datetime

from ha_assist_core import custom_intents


def before_scenario(context, scenario):
    custom_intents.datetime = datetime
    if "skip" in scenario.effective_tags:
        scenario.skip("Сценарий фиксирует будущее ожидаемое поведение.")
    context.ha_objects = []
    context.areas = []
    context.floors = []
    context.source_area_id = None
    context.source_area_name = None
    context.source_floor_id = None
    context.source_floor_name = None
    context.previous_exchange = None
