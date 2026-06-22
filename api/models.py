from django.db import models

ROLE_CHOICES = (
    ('admin', '管理员'),
    ('experimenter', '实验员'),
    ('auditor', '审核人'),
    ('calibrator', '校准员'),
)

STATUS_CHOICES = (
    ('pending_submit', '待提交'),
    ('pending_audit', '待审核'),
    ('pending_calibration', '待校准'),
    ('calibrating', '校准中'),
    ('pending_acceptance', '待验收'),
    ('deviation_pending', '偏差待处理'),
    ('rejected', '已驳回'),
    ('closed', '已结案'),
)

AUDIT_RESULT_CHOICES = (
    ('approved', '通过'),
    ('returned', '退回'),
    ('rejected', '驳回'),
)

DEVIATION_LEVEL_CHOICES = (
    ('none', '无偏差'),
    ('minor', '轻微偏差'),
    ('major', '严重偏差'),
    ('critical', '重大偏差'),
)

ACCESSORY_STATUS_CHOICES = (
    ('normal', '正常'),
    ('damaged', '损坏'),
    ('missing', '缺失'),
    ('replaced', '已更换'),
)

WARNING_LEVEL_CHOICES = (
    ('approaching', '临近到期'),
    ('expired', '已到期'),
    ('overdue', '超期未处理'),
)

WARNING_STATUS_CHOICES = (
    ('unhandled', '未处理'),
    ('processing', '处理中'),
    ('handled', '已处理'),
)
