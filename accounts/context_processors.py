def notifications_count(request):
    if request.user.is_authenticated:
        count = request.user.notifications.filter(is_read=False).count()
        recent = request.user.notifications.all()[:6]
        return {'unread_notifications': count, 'recent_notifications': recent}
    return {'unread_notifications': 0, 'recent_notifications': []}
