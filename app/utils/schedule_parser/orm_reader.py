import re
import os.path
import datetime
import traceback
from unicodedata import name
from venv import create
import xlrd

import datetime as dt
from datetime import datetime
from sqlalchemy.orm import Session
from itertools import cycle

from .get_or_create import get_or_create
from ...database import models
from .formatters import format_lesson_type, format_name, format_room_name, format_teacher_name


class Reader:

    def __init__(self, db: Session):
        self.weeks_count = 16
        self.db = db
        offset = dt.timedelta(hours=3)
        time_zone = dt.timezone(offset, name='МСК')
        self.today = datetime.now(tz=time_zone)

        try:
            self.weeks_count = int(self.db.query(models.WorkingData).filter_by(
                name="weeks_count").first().value)

        except Exception as err:
            
            self.weeks_count = int(get_or_create(session=self.db, model=models.WorkingData,
                                                name="weeks_count", value="16").value)

            print("weeks_count ERROR! -> ", err)


        self.notes_dict = {
            'МП-1': 4,
            'В-78': 1,
            'В-86': 2,
            'В78': 1,
            'С-20': 3,
            'СГ': 5,
            'СГ-22': 5,
        }

        self.days_dict = {
            'ПОНЕДЕЛЬНИК': 1,
            'ВТОРНИК': 2,
            'СРЕДА': 3,
            'ЧЕТВЕРГ': 4,
            'ПЯТНИЦА': 5,
            'СУББОТА': 6
        }

        self.time_dict = {
            "9:00": 1,
            "10:40": 2,
            "12:40": 3,
            "14:20": 4,
            "16:20": 5,
            "18:00": 6,
            "19:40": 7,
            "18:30": 8,
            "20:10": 9
        }

        self.lesson_types = {
            "лк": 1,
            "лек": 1,
            "пр": 2,
            "лр": 3,
            "лаб": 3,
            "срс": 8,
            "": None,
        }

        self.periods = {
            "semester": 1,
            "credits": 2,
            "exams": 3
        }

        self.current_place = 1
        self.current_period = 1
        # print("Reader initialized")

    def run(self, xlsx_dir):

        for path, dirs, files in os.walk(xlsx_dir):
            print("path1", path)
            for file_name in files:

                temp_file_name = file_name.lower()
                if "стром" in temp_file_name or "кбисп" in temp_file_name or "икб" in temp_file_name or ("иту" in temp_file_name and ("сем" in temp_file_name or "маг_оч" in temp_file_name)):
                    self.current_place = 3
                elif "итхт" in temp_file_name:
                    self.current_place = 2
                else:
                    self.current_place = 1
                try:
                    if ("\\") in path:
                        self.current_period = self.periods[path.split("\\")[-1]]
                    else:
                        self.current_period = self.periods[path.split("/")[-1]]
                except Exception as e:
                    print(e, "ex in current_period")
                    continue
                # print("current_period -> ", self.current_period)
                path_to_xlsx_file = os.path.join(path, file_name)
                print(path_to_xlsx_file)
                # if("ИКиб_маг_2к" in path_to_xlsx_file):
                #     continue

                try:
                    self.read(path_to_xlsx_file)
                    # TODO move truncate here
                    self.db.commit()
                except Exception as err:
                    print(err, traceback.format_exc(), "in", file_name)
                    continue

    def write_to_db(self, timetable):

        def add_weeks(weeks, lesson):
            for week in weeks:
                week_l = models.SpecificWeek(
                    secific_week=week, lesson_id=lesson)
                self.db.add(week_l)

        def get_group_degree(group):
            if group[2] == "Б":
                degree = 1

            elif group[2] == "М":
                degree = 2

            elif group[2] == "С":
                degree = 3
            else:
                degree = 1
                print("What is", group)

            return degree

        def get_group_year(group):
            today = self.today
            offset = 0
            current_year = today.year % 2000
            if today.month > 8 and today.day > 20:
                current_year += 1

            year = 1
            try:
                y = int(group[-2] + group[-1])
                year = current_year - y
            except Exception as e:
                print(group, e)

            return year

        def data_append_to_lesson(group, period, teacher, day_num,
                                  call,
                                  week, lesson_type, room, is_usual_place, discipline_name):

            # print(discipline_name)
            weeks = list(discipline_name[1])
            weeks.sort()

            less = ""

            # print(discipline_name[0])
            room_id = None
            if room:
                room_id = room.id
            every_week = not weeks
            discipline = get_or_create(
                session=self.db, model=models.Discipline, name=discipline_name[0])
            self.db.flush()

            created = True

            if lesson_type == 1:
                query = self.db.query(models.Lesson).filter_by(call_id=call,
                                                               period_id=period,
                                                               lesson_type_id=lesson_type,
                                                               discipline_id=discipline.id,
                                                               room_id=room_id,
                                                               day_of_week=day_num,
                                                               is_usual_place=is_usual_place,
                                                               every_week=every_week,
                                                               week=week)
                
                if teacher:
                    query = query.join(models.Lesson.teachers.and_(
                        models.Teacher.id == teacher[0].id))

                instance = query.first()

                if instance:
                    created = False
                    lesson = instance
                    # if "Линейная алгебра и аналитическая геометрия" in instance.discipline.name:
                    #     print(group.name, instance.discipline.name, instance.day_of_week, instance.week, instance.call_id, instance.teachers)
                    #     print(teacher)
                else:
                    lesson = models.Lesson(call_id=call,
                                           period_id=period,
                                           lesson_type_id=lesson_type,
                                           discipline_id=discipline.id,
                                           room_id=room_id,
                                           day_of_week=day_num,
                                           is_usual_place=is_usual_place,
                                           every_week=every_week,
                                           week=week)
                    # lesson.teachers.append(teacher[0])

            else:
                lesson = models.Lesson(call_id=call,
                                       period_id=period,
                                       lesson_type_id=lesson_type,
                                       discipline_id=discipline.id,
                                       room_id=room_id,
                                       day_of_week=day_num,
                                       is_usual_place=is_usual_place,
                                       every_week=every_week,
                                       week=week)

            self.db.add(lesson)
            self.db.flush()
            if created:
                add_weeks(weeks, lesson.id)

            for t in teacher:
                lesson.teachers.append(t)
            lesson.groups.append(group)
            for sub in discipline_name[2]:
                try:
                    subgroup = models.Subgroup(
                        subgroup=sub, lesson_id=lesson.id)
                    self.db.add(subgroup)
                    self.db.flush()
                except:
                    self.db.rollback()
                    print("----------")
                    print("ROLLBACK ON SUBGROUP APPEND")
                    print("----------")
        stack = ""

        for group_name, value in sorted(timetable.items()):
            try:
                group_name = re.findall(r"([А-Я]+-\w+-\w+)", group_name, re.I)
                if len(group_name) > 0:
                    print("Add schedule for ", group_name)
                    group_name = group_name[0]


                    group = get_or_create(session=self.db,
                                          model=models.Group,
                                          name=group_name,
                                          year=get_group_year(group_name),
                                          degree_id=get_group_degree(group_name))
                    

                for n_day, day_item in sorted(value.items()):

                    for n_lesson, lesson_item in sorted(day_item.items()):
                        for n_week, item in sorted(lesson_item.items()):
                            day_num = n_day.split("_")[1]
                            call_num = n_lesson.split("_")[1]

                            week = n_week.split("_")[1]
                            for dist in item:

                                lesson_type = None

                                if dist['type']:
                                    if "пр" in dist['type'].lower():
                                        lesson_type = self.lesson_types["пр"]
                                    elif "лк" in dist['type'].lower() or "лек" in dist['type'].lower():
                                        lesson_type = self.lesson_types["лк"]
                                    elif "лаб" in dist['type'].lower() or "лр" in dist['type'].lower():
                                        lesson_type = self.lesson_types["лр"]
                                    elif "срс" in dist['type'].lower() or "с/р" in dist['type'].lower():
                                        lesson_type = self.lesson_types["срс"]

                                is_usual_place = True

                                if dist['teacher']:
                                    teacher = [get_or_create(
                                        session=self.db, model=models.Teacher, name=t) for t in dist['teacher'] if t]
                                else:
                                    teacher = None
                                if dist['room']:
                                    room = get_or_create(
                                        session=self.db, model=models.Room, name=dist['room'][0], place_id=dist['room'][1])
                                    if room.place_id == self.current_place or not room.place_id:
                                        is_usual_place = True
                                    else:
                                        is_usual_place = False

                                else:
                                    room = None

                                self.db.flush()

                                # print(is_usual_place, room, room.place_id, self.current_place)
                                
                                data_append_to_lesson(group, self.current_period, teacher,
                                                      day_num,
                                                      call_num,
                                                      week, lesson_type, room, is_usual_place, dist['name'])
            except Exception as e:
                self.db.rollback()
                print("----------")
                print("ROLLBACK ON SCHEDULE APPEND")
                print("Reason: ", e)
                print("----------")

    def read_one_group_for_semester(self, sheet, discipline_col_num, group_name_row_num, cell_range):
        """
            Получение расписания одной группы
            discipline_col_num(int): Номер столбца колонки 'Предмет'
            range(dict): Диапазон выбора ячеек
        """
        one_group = {}
        group_name = sheet.cell(
            group_name_row_num, discipline_col_num).value  # Название группы
        one_group[group_name] = {}  # Инициализация словаря

        # перебор по дням недели (понедельник-суббота)
        # номер дня недели (1-6)
        for day_num in cell_range:
            one_day = {}

            for lesson_range in cell_range[day_num]:
                lesson_num = lesson_range[0]
                time = lesson_range[1]

                if "18:30" in time:
                    lesson_num = 8
                if "20:10" in time:
                    lesson_num = 9
                week_num = lesson_range[2]
                string_index = lesson_range[3]

                # Перебор одного дня (1-6 пара)
                if "lesson_{}".format(lesson_num) not in one_day:
                    one_day["lesson_{}".format(lesson_num)] = {}

                # Получение данных об одной паре
                tmp_name = str(sheet.cell(
                    string_index, discipline_col_num).value)
                # if lesson_num ==  9:
                #     print(time, group_name, tmp_name, day_num)
                tmp_name = format_name(tmp_name, week_num, self.weeks_count)

                if isinstance(tmp_name, list) and tmp_name:

                    lesson_type = format_lesson_type(sheet.cell(
                        string_index, discipline_col_num + 1).value)

                    # correct_max_len = max(len(tmp_name), len(lesson_type))

                    teacher = format_teacher_name(sheet.cell(
                        string_index, discipline_col_num + 2).value)
                    room = format_room_name(sheet.cell(
                        string_index, discipline_col_num + 3).value, self.notes_dict, self.current_place)

                    # TODO need to fix
                    max_len = max(len(tmp_name), len(room), len(lesson_type))

                    if len(tmp_name) < max_len:
                        tmp_name = cycle(tmp_name)
                    if len(room) < max_len:
                        room = cycle(room)
                    if len(lesson_type) < max_len:
                        lesson_type = cycle(lesson_type)

                    if len(teacher) > max_len and max_len == 1:
                        lesson_tuple = [
                            (tmp_name[0], [t for t in teacher], room[0], lesson_type[0])]
                    else:
                        teacher = cycle([[t] for t in teacher])
                        lesson_tuple = list(
                            zip(tmp_name, teacher, room, lesson_type))

                    for tuple_item in lesson_tuple:
                        name = tuple_item[0]
                        teacher = tuple_item[1]
                        room = tuple_item[2]
                        lesson_type = tuple_item[3]

                        one_lesson = {"date": None, "time": time, "name": name, "type": lesson_type,
                                      "teacher": teacher, "room": room}

                        if name:
                            if "week_{}".format(week_num) not in one_day["lesson_{}".format(lesson_num)]:
                                one_day["lesson_{}".format(lesson_num)][
                                    "week_{}".format(week_num)] = []  # Инициализация списка
                            one_day["lesson_{}".format(lesson_num)]["week_{}".format(
                                week_num)].append(one_lesson)

                    # Объединение расписания
                    one_group[group_name]["day_{}".format(day_num)] = one_day
        # print(one_group)
        return one_group

    def read(self, xlsx_path):
        """

        """

        def get_column_range_for_type_eq_semester(xlsx_sheet, group_name_cell, group_name_row_index):
            week_range = {
                1: [],
                2: [],
                3: [],
                4: [],
                5: [],
                6: []
            }

            # Номер строки, с которой начинается отсчет пар
            initial_row_num = group_name_row_index + 1
            lesson_count = 0  # Счетчик количества пар
            # Перебор столбца с номерами пар и вычисление на основании количества пар в день диапазона выбора ячеек
            day_num_val, lesson_num_val, lesson_time_val, lesson_week_num_val = 0, 0, 0, 0
            row_s = len(xlsx_sheet.col(group_name_row.index(group_name_cell)))

            for lesson_num in range(initial_row_num, row_s):

                day_num_col = xlsx_sheet.cell(
                    lesson_num, group_name_row.index(group_name_cell) - 5)

                if day_num_col.value != '':
                    day_num_val = self.days_dict[day_num_col.value.upper()]

                lesson_num_col = xlsx_sheet.cell(
                    lesson_num, group_name_row.index(group_name_cell) - 4)
                if lesson_num_col.value != '':
                    lesson_num_val = lesson_num_col.value
                    if isinstance(lesson_num_val, float):
                        lesson_num_val = int(lesson_num_val)
                        if lesson_num_val > lesson_count:
                            lesson_count = lesson_num_val

                lesson_time_col = xlsx_sheet.cell(
                    lesson_num, group_name_row.index(group_name_cell) - 3)
                if lesson_time_col.value != '':
                    lesson_time_val = str(
                        lesson_time_col.value).replace('-', ':')

                lesson_week_num = xlsx_sheet.cell(
                    lesson_num, group_name_row.index(group_name_cell) - 1)
                if lesson_week_num.value != '':
                    if lesson_week_num.value == 'I':
                        lesson_week_num_val = 1
                    elif lesson_week_num.value == 'II':
                        lesson_week_num_val = 2
                else:
                    if lesson_week_num_val == 1:
                        lesson_week_num_val = 2
                    else:
                        lesson_week_num_val = 1

                lesson_string_index = lesson_num

                if re.findall(r'\d+:\d+', str(lesson_time_val), flags=re.A):
                    lesson_range = (lesson_num_val, lesson_time_val,
                                    lesson_week_num_val, lesson_string_index)
                    week_range[day_num_val].append(lesson_range)
            return week_range

        book = xlrd.open_workbook(xlsx_path)
        # print(book)
        sheet = book.sheet_by_index(0)
        DOC_TYPE_EXAM = 2
        column_range = []
        timetable = {}
        group_list = []

        # Индекс строки с названиями групп
        group_name_row_num = 1
        # TODO find by name of groups

        for row_index in range(len(sheet.col(1))):
            group_name_row = sheet.row_values(row_index)
            if len(group_name_row) > 0:
                group_row_str = " ".join(str(x) for x in group_name_row)
                gr = re.findall(r'([А-Я]+-\w+-\w+)', group_row_str, re.I)
                if gr:

                    group_name_row_num = row_index
                    break

        group_name_row = sheet.row(group_name_row_num)

        for group_cell in group_name_row:  # Поиск названий групп
            group = str(group_cell.value)
            group = re.search(r'([А-Я]+-\w+-\w+)', group)
            if group:  # Если название найдено, то получение расписания этой группы
                if ("ТЛБО" in group.group(0) or "ЭСБО" in group.group(0)) and self.current_place == 2:
                    print("! ТЛБО or ЭСБО in group and current_place == 2")
                    continue
                # обновляем column_range, если левее группы нет разметки с неделями, используем старый
                if not group_list:

                    if self.current_period == 3:
                        continue

                    elif self.current_period == 2 and self.current_place == 2:
                        continue

                    elif self.current_period == 2:
                        continue

                    else:
                        column_range = get_column_range_for_type_eq_semester(
                            sheet, group_cell, group_name_row_num)

                print(group.group(0))

                group_list.append(group.group(0))
        
        # Очистка старого расписания, если они есть
        print(group_list)
        for group_name in group_list:
            instance = self.db.query(models.Group).filter_by(name=group_name).first()
            if instance:
                lessons = instance.lessons
                for lesson in lessons:
                    self.db.delete(lesson)
        self.db.commit()

        for group_cell in group_name_row:  # Поиск названий групп
            group = str(group_cell.value)
            group = re.search(r'([А-Я]+-\w+-\w+)', group)
            if group:  # Если название найдено, то получение расписания этой группы
                if ("ТЛБО" in group.group(0) or "ЭСБО" in group.group(0)) and self.current_place == 2:
                    print("! ТЛБО or ЭСБО in group and current_place == 2")
                    continue
                # обновляем column_range, если левее группы нет разметки с неделями, используем старый
                if not group_list:

                    if self.current_period == 3:
                        continue

                    elif self.current_period == 2 and self.current_place == 2:
                        continue

                    elif self.current_period == 2:
                        continue

                    else:
                        column_range = get_column_range_for_type_eq_semester(
                            sheet, group_cell, group_name_row_num)

                one_time_table = {}

                if self.current_period == 3:
                    pass

                elif self.current_period == 2 and self.current_place == 2:
                    pass

                elif self.current_period == 2:
                    pass
                    
                else:
                    one_time_table = self.read_one_group_for_semester(
                        sheet, group_name_row.index(group_cell), group_name_row_num, column_range)  # По номеру столбца

                for key in one_time_table.keys():
                    # Добавление в общий словарь
                    timetable[key] = one_time_table[key]

        self.write_to_db(timetable)
        book.release_resources()
        del book
        return group_list
