from django.db import models
from django.contrib.auth.models import User
from django.db.models import Avg, StdDev

class Club(models.Model):
    """Represents a single golf club in a user's bag."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, help_text="e.g., Driver, 7 Iron, Pitching Wedge")

    def __str__(self):
        return self.name

    def get_average_distance(self):
        """Calculates the average distance for this club across all shots."""
        avg = self.shot_set.aggregate(average=Avg('distance'))['average']
        return round(avg, 1) if avg else 0

    def get_distance_std_dev(self):
        """Calculates the standard deviation of distance for this club."""
        stddev = self.shot_set.aggregate(stddev=StdDev('distance'))['stddev']
        return round(stddev, 1) if stddev else 0

    def get_average_distance_fairway(self):
        """Calculates average distance for Fairway and Tee Box shots (excludes Sand and Rough)."""
        avg = self.shot_set.filter(lie__in=['Fairway', 'Tee Box']).aggregate(average=Avg('distance'))['average']
        return int(round(avg)) if avg else None

    def get_average_distance_rough(self):
        """Calculates average distance for Rough shots only (excludes Sand, Fairway, Tee Box)."""
        avg = self.shot_set.filter(lie='Rough').aggregate(average=Avg('distance'))['average']
        return int(round(avg)) if avg else None

    def get_fairway_shot_count(self):
        """Returns count of shots from Fairway and Tee Box."""
        return self.shot_set.filter(lie__in=['Fairway', 'Tee Box']).count()

    def get_rough_shot_count(self):
        """Returns count of shots from Rough."""
        return self.shot_set.filter(lie='Rough').count()

class GolfRound(models.Model):
    """Represents a single round of golf played by a user."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    course_name = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.course_name} on {self.date}"

class Shot(models.Model):
    """Represents a single shot taken during a round."""
    # Enums for choices to ensure data consistency
    SHOT_SHAPE_CHOICES = [('Straight', 'Straight'), ('Fade', 'Fade'), ('Draw', 'Draw'), ('Slice', 'Slice'), ('Hook', 'Hook')]
    LIE_CHOICES = [('Fairway', 'Fairway'), ('Rough', 'Rough'), ('Sand', 'Sand'), ('Tee Box', 'Tee Box')]

    golf_round = models.ForeignKey(GolfRound, on_delete=models.CASCADE)
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    distance = models.PositiveIntegerField(help_text="Distance in yards")
    shot_shape = models.CharField(max_length=10, choices=SHOT_SHAPE_CHOICES)
    lie = models.CharField(max_length=10, choices=LIE_CHOICES)

    def __str__(self):
        return f"{self.club.name} - {self.distance} yards"

class LaunchMonitorImport(models.Model):
    """Tracks launch monitor data imports for audit and debugging."""
    DEVICE_CHOICES = [
        ('Garmin R10', 'Garmin R10'),
        ('SkyTrak+', 'SkyTrak+'),
        ('Flightscope Mevo+', 'Flightscope Mevo+'),
        ('Arccos Caddie', 'Arccos Caddie'),
        ('Generic Launch Monitor', 'Generic Launch Monitor'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('parsing', 'Parsing'),
        ('preview', 'Preview Ready'),
        ('imported', 'Imported'),
        ('failed', 'Failed'),
        ('partial', 'Partially Imported'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    device_type = models.CharField(max_length=50, choices=DEVICE_CHOICES)
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    raw_data = models.TextField(help_text="Original file content (JSON) for debugging")
    parsed_data = models.JSONField(null=True, blank=True, help_text="Normalized parsed data")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_log = models.TextField(blank=True, help_text="Parsing errors and warnings")
    rounds_created = models.PositiveIntegerField(default=0)
    shots_created = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    imported_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.device_type} import - {self.file_name} ({self.status})"

