from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db.models import Max
from django.template.defaultfilters import floatformat
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy

from judge.contest_format.default import DefaultContestFormat
from judge.contest_format.registry import register_contest_format
from judge.utils.timedelta import nice_repr


@register_contest_format('codebreaker')
class CodebreakerContestFormat(DefaultContestFormat):
    name = gettext_lazy('Codebreaker')
    config_defaults = {'penalty': 1}
    config_validators = {'penalty': lambda x: x >= 0}
    '''
        penalty: The points lost by a "Input did not break code" result.
    '''

    @classmethod
    def validate(cls, config):
        if config is None:
            return

        if not isinstance(config, dict):
            raise ValidationError('Codebreaker-styled contest expects no config or dict as config')

        for key, value in config.items():
            if key not in cls.config_defaults:
                raise ValidationError('unknown config key "%s"' % key)
            if not isinstance(value, type(cls.config_defaults[key])):
                raise ValidationError('invalid type for config key "%s"' % key)
            if not cls.config_validators[key](value):
                raise ValidationError('invalid value "%s" for config key "%s"' % (value, key))

    def __init__(self, contest, config):
        self.config = self.config_defaults.copy()
        self.config.update(config or {})
        self.contest = contest

    def update_participation(self, participation):
        cumtime = 0
        score = 0
        format_data = {}

        probs = participation.submissions.values_list('problem_id', flat=True).distinct()

        for prob in probs:
            subs = participation.submissions.exclude(submission__result__isnull=True) \
                                .exclude(submission__result__in=['IE', 'CE']) \
                                .filter(problem_id=prob).order_by('submission__date')
            penalty = 0
            points = 0
            ac = False
            for sub in subs:
                dt = (sub.submission.date - participation.start).total_seconds()
                if sub.points!=0:
                    ac = True
                    points = sub.points
                    break
                feedback = sub.submission.test_cases.all()[0].feedback
                if feedback == "Insane Input":
                    continue
                penalty+=1
            points -= penalty*self.config['penalty']
            if ac: 
                points=max(points, 0) # don't want negative after ac
                score += points # penalty doesn't count if not ac
            cumtime += dt
            format_data[str(prob)] = {'time': dt, 'points': points}

        participation.cumtime = max(cumtime, 0)
        participation.score = score
        participation.tiebreaker = 0
        participation.format_data = format_data
        participation.save()

    @classmethod
    def best_solution_state(cls, points, total):
        if points < 0:
            return 'failed-score'
        if points == total:
            return 'full-score'
        return 'partial-score'


