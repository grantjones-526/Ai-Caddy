"""
Handles the application's backend logic.
Each function corresponds to a page or an API endpoint, processing
requests and interacting with the database models.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout
from django.conf import settings
from .models import Club, GolfRound, Shot
import os
import csv
import statistics

# --- Authentication Views ---
def signup_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            # Add a default set of clubs for a new user
            default_clubs = ['Driver', '3 Wood', '5 Wood', '4 Iron', '5 Iron', '6 Iron', '7 Iron', '8 Iron', '9 Iron', 'Pitching Wedge', '52 Degree', '56 Degree', '60 Degree']
            for club_name in default_clubs:
                Club.objects.create(user=user, name=club_name)
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'registration/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')

# --- Main Application Views ---
@login_required
def dashboard_view(request):
    """Displays user's clubs and their average performance."""
    clubs = Club.objects.filter(user=request.user)
    rounds = GolfRound.objects.filter(user=request.user).order_by('-date')
    return render(request, 'dashboard/dashboard.html', {'clubs': clubs, 'rounds': rounds})

@login_required
def add_round_view(request):
    """Handles the creation of a new round and its associated shots."""
    if request.method == 'POST':
        course_name = request.POST.get('course_name')
        new_round = GolfRound.objects.create(user=request.user, course_name=course_name)

        # Process multiple shots submitted with the form
        clubs_ids = request.POST.getlist('club')
        distances = request.POST.getlist('distance')
        shot_shapes = request.POST.getlist('shot_shape')
        lies = request.POST.getlist('lie')

        for i in range(len(clubs_ids)):
            if distances[i]: # Only save if distance is entered
                Shot.objects.create(
                    golf_round=new_round,
                    club_id=clubs_ids[i],
                    distance=int(distances[i]),
                    shot_shape=shot_shapes[i],
                    lie=lies[i]
                )
        return redirect('round_detail', round_id=new_round.id)

    clubs = Club.objects.filter(user=request.user)
    return render(request, 'dashboard/addround.html', {'clubs': clubs})

@login_required
def round_detail_view(request, round_id):
    """Displays the details and shots of a specific round."""
    golf_round = get_object_or_404(GolfRound, id=round_id, user=request.user)
    shots = Shot.objects.filter(golf_round=golf_round).order_by('id')
    return render(request, 'dashboard/round_detail.html', {'round': golf_round, 'shots': shots})

@login_required
def recommendation_view(request):
    """The core AI Caddy feature: recommends a club based on distance and lie."""
    context = {}
    if 'distance' in request.GET:
        try:
            distance_to_hole = int(request.GET.get('distance'))
            lie = request.GET.get('lie')
            context['distance_input'] = distance_to_hole
            context['lie_input'] = lie

            clubs = Club.objects.filter(user=request.user)
            recommendations = []
            for club in clubs:
                print(f"--- Checking Club: {club.name}, Lies: '{lie}' ---")
                shots = Shot.objects.filter(club=club, lie=lie)
                print(f"Found {shots.count()} shots matching")
                if shots.count() > 2: # Need at least 3 shots for a meaningful recommendation
                    shot_distances = list(shots.values_list('distance', flat=True))
                    avg_dist = statistics.mean(shot_distances)
                    std_dev = statistics.stdev(shot_distances)

                    # Simple model: a club is a candidate if the target distance is within one standard deviation of its average
                    if (avg_dist - std_dev) <= distance_to_hole <= (avg_dist + std_dev):
                        recommendations.append({
                            'club_name': club.name,
                            'avg_dist': round(avg_dist, 1),
                            'confidence': 'High' if abs(avg_dist - distance_to_hole) < (std_dev / 2) else 'Medium'
                        })
            
            # Sort by which club's average is closest to the target distance
            recommendations.sort(key=lambda x: abs(x['avg_dist'] - distance_to_hole))
            context['recommendations'] = recommendations
        except (ValueError, TypeError):
            context['error'] = "Please enter a valid distance."

    return render(request, 'dashboard/recommendations.html', context)

@login_required
def load_test_data_view(request):
    """
    Reads a predefined CSV from the project folder and populates
    shot data for the currently logged-in user.
    """
    
    # 1. Define the path to the CSV file
    file_path = os.path.join(settings.BASE_DIR, 'dummy_shots.csv')

    # 2. Check if the file actually exists
    if not os.path.exists(file_path):
        # You could use Django's message framework to report an error
        # messages.error(request, "Dummy data file not found.")
        return redirect('dashboard') # Go back to the dashboard

    # 3. Create a new round for this test data
    new_round = GolfRound.objects.create(
        user=request.user, 
        course_name="Test Data Load"
    )

    # 4. Get the user's clubs into a dictionary for fast lookup
    # This turns [Club(name='Driver'), Club(name='7 Iron')]
    # into {'Driver': ClubObject, '7 Iron': ClubObject}
    user_clubs = {club.name: club for club in Club.objects.filter(user=request.user)}
    
    shots_to_create = []

    # 5. Read the CSV file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            golf_RD = new_round
            for row in reader:
                club_name = row.get('club_name')
                
                # Find the user's *actual* club object that matches the name
                club = user_clubs.get(club_name)
 
                # 6. Only create a shot if the user has that club and distance is valid
                if club and row.get('distance'):
                    try:
                        shots_to_create.append(
                            Shot(
                                golf_round=golf_RD,
                                club=club, # Use the club object we found
                                distance=int(row.get('distance')),
                                shot_shape=row.get('shot_shape', 'Straight'),
                                lie=row.get('lie', 'Fairway')
                            )
                        )
                    except (ValueError, TypeError):
                        # Skip row if distance isn't a valid number
                        pass

        # 7. Use bulk_create to add all shots to the DB in one query
        if shots_to_create:
            Shot.objects.bulk_create(shots_to_create)
        
        # 8. Redirect to the new round's detail page
        return redirect('round_detail', round_id=new_round.id)
        
    except Exception as e:
        # Handle file read errors
        # messages.error(request, f"Error reading CSV: {e}")
        return redirect('dashboard')