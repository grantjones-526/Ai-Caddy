"""
Handles the application's backend logic.
Each function corresponds to a page or an API endpoint, processing
requests and interacting with the database models.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib import messages
from django.conf import settings
from .models import Club, GolfRound, Shot
import os
import csv
import statistics
import numpy as np
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.decomposition import PCA
from django.http import JsonResponse

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
    """
    The core AI Caddy feature: recommends a club using KNN algorithm.
    Uses distance, lie, bend, and shot_shape as features with flexibility to add more.
    """
    context = {}
    if 'distance' in request.GET:
        try:
            distance_to_hole = int(request.GET.get('distance'))
            lie = request.GET.get('lie', 'Fairway')
            bend = request.GET.get('bend', 'Straight')
            shot_shape = request.GET.get('shot_shape', 'Straight')  # Optional: can add to form later
            
            context['distance_input'] = distance_to_hole
            context['lie_input'] = lie
            context['bend_input'] = bend
            context['shot_shape_input'] = shot_shape

            # Get all user's historical shots
            user_shots = Shot.objects.filter(club__user=request.user)
            
            if user_shots.count() < 3:
                context['error'] = "Not enough shot data. You need at least 3 shots to get recommendations."
                return render(request, 'dashboard/recommendations.html', context)

            # Helper function to infer bend from shot_shape for historical data
            def infer_bend_from_shot_shape(shot_shape):
                """Infer hole bend from shot shape used historically."""
                if shot_shape in ['Draw', 'Hook']:
                    return 'Dogleg Left'  # Used draw/hook to go left
                elif shot_shape in ['Fade', 'Slice']:
                    return 'Dogleg Right'  # Used fade/slice to go right
                else:
                    return 'Straight'  # Straight shot, no bend needed

            # Prepare training data: features (distance, lie, bend, shot_shape) and target (club)
            features_list = []
            clubs_list = []
            
            for shot in user_shots:
                # Infer bend from shot_shape for historical shots
                inferred_bend = infer_bend_from_shot_shape(shot.shot_shape)
                
                features_list.append([
                    shot.distance,      # Feature 1: Distance (numeric)
                    shot.lie,           # Feature 2: Lie (categorical - will be encoded)
                    inferred_bend,      # Feature 3: Bend (inferred from shot_shape) (categorical - will be encoded)
                    shot.shot_shape     # Feature 4: Shot Shape (categorical - will be encoded)
                    # Easy to add more features here in the future
                ])
                clubs_list.append(shot.club.name)  # Target: which club was used
            
            if not features_list:
                context['error'] = "No shot data available for recommendations."
                return render(request, 'dashboard/recommendations.html', context)

            # Encode categorical features
            # Extract numeric and categorical columns
            features_array = np.array(features_list)
            distance_col = features_array[:, 0].astype(float).reshape(-1, 1)
            lie_col = features_array[:, 1]
            bend_col = features_array[:, 2]
            shot_shape_col = features_array[:, 3]
            
            # Encode lie, bend, and shot_shape
            lie_encoder = LabelEncoder()
            bend_encoder = LabelEncoder()
            shot_shape_encoder = LabelEncoder()
            
            lie_encoded = lie_encoder.fit_transform(lie_col).reshape(-1, 1)
            bend_encoded = bend_encoder.fit_transform(bend_col).reshape(-1, 1)
            shot_shape_encoded = shot_shape_encoder.fit_transform(shot_shape_col).reshape(-1, 1)
            
            # Combine all features: distance (numeric) + encoded lie + encoded bend + encoded shot_shape
            X_train = np.hstack([distance_col, lie_encoded, bend_encoded, shot_shape_encoded])
            
            # Encode club names (target variable)
            club_encoder = LabelEncoder()
            y_train = club_encoder.fit_transform(clubs_list)
            
            # Prepare query point (current situation)
            try:
                lie_encoded_query = lie_encoder.transform([lie])[0]
            except ValueError:
                # If lie not in training data, use most common lie
                lie_encoded_query = lie_encoder.transform([lie_encoder.classes_[0]])[0]
            
            try:
                bend_encoded_query = bend_encoder.transform([bend])[0]
            except ValueError:
                # If bend not in training data, use most common bend
                bend_encoded_query = bend_encoder.transform([bend_encoder.classes_[0]])[0]
            
            try:
                shot_shape_encoded_query = shot_shape_encoder.transform([shot_shape])[0]
            except ValueError:
                # If shot_shape not in training data, use most common shot_shape
                shot_shape_encoded_query = shot_shape_encoder.transform([shot_shape_encoder.classes_[0]])[0]
            
            X_query = np.array([[distance_to_hole, lie_encoded_query, bend_encoded_query, shot_shape_encoded_query]])
            
            # Determine optimal k (number of neighbors)
            # Use sqrt of sample size, but at least 3 and at most 10
            k = max(3, min(10, int(np.sqrt(len(X_train)))))
            
            # Train KNN classifier
            knn = KNeighborsClassifier(n_neighbors=k, weights='distance')
            knn.fit(X_train, y_train)
            
            # Get predictions and distances to neighbors
            neighbor_distances, neighbor_indices = knn.kneighbors(X_query, n_neighbors=min(k, len(X_train)))
            
            # Get the predicted club
            predicted_club_encoded = knn.predict(X_query)[0]
            predicted_club = club_encoder.inverse_transform([predicted_club_encoded])[0]
            
            # Calculate better confidence scores based on distance-weighted agreement
            # Get actual club names of neighbors
            neighbor_clubs = [clubs_list[i] for i in neighbor_indices[0]]
            neighbor_dists = neighbor_distances[0]
            
            # Calculate weighted scores for each club based on inverse distance
            # Closer neighbors have more weight
            club_scores = {}
            total_weight = 0
            
            for i, club in enumerate(neighbor_clubs):
                # Use inverse distance as weight (add small epsilon to avoid division by zero)
                weight = 1.0 / (neighbor_dists[i] + 0.0001)
                total_weight += weight
                
                if club not in club_scores:
                    club_scores[club] = 0
                club_scores[club] += weight
            
            # Normalize scores to probabilities (0-1 range)
            # But also factor in the average distance to neighbors for overall confidence
            avg_neighbor_distance = np.mean(neighbor_dists)
            max_possible_distance = np.max(neighbor_dists) if len(neighbor_dists) > 0 else 1
            
            # Calculate confidence factor (0-1) based on how close neighbors are
            # Closer neighbors = higher confidence
            distance_confidence = 1.0 / (1.0 + avg_neighbor_distance / max_possible_distance)
            
            # Normalize club scores to percentages, but cap at 95% to show uncertainty
            club_probabilities = {}
            for club, score in club_scores.items():
                raw_prob = score / total_weight if total_weight > 0 else 0
                # Apply confidence factor - if neighbors are far, reduce confidence
                adjusted_prob = raw_prob * (0.7 + 0.3 * distance_confidence)  # Scale between 0.7-1.0
                # Cap at 95% to always show some uncertainty
                club_probabilities[club] = min(0.95, adjusted_prob)
            
            # Get probabilities for all clubs (for display purposes)
            # Include all clubs that appeared in training, not just neighbors
            all_club_probs = knn.predict_proba(X_query)[0]
            all_club_probabilities = {
                club_encoder.inverse_transform([i])[0]: prob 
                for i, prob in enumerate(all_club_probs)
            }
            
            # Merge - use distance-weighted for neighbors, scale down others
            final_probabilities = {}
            for club in all_club_probabilities:
                if club in club_probabilities:
                    # Use distance-weighted probability
                    final_probabilities[club] = club_probabilities[club]
                else:
                    # Scale down non-neighbor probabilities
                    final_probabilities[club] = all_club_probabilities[club] * 0.3
            
            # Get nearest neighbors details for recommendations
            recommendations = []
            seen_clubs = set()
            
            # Sort clubs by probability (highest first)
            sorted_clubs = sorted(final_probabilities.items(), key=lambda x: x[1], reverse=True)
            
            # Get club objects for easier access to model methods
            club_objects = {club.name: club for club in Club.objects.filter(user=request.user)}
            
            # Add top recommendations (sorted by probability)
            for club_name, prob in sorted_clubs:
                if club_name not in seen_clubs and prob > 0.01:  # At least 1% probability
                    # Get the club object
                    club_obj = club_objects.get(club_name)
                    
                    # Calculate average distance based on the selected lie
                    # If lie is Fairway or Tee Box, use fairway average; if Rough, use rough average
                    if lie in ['Fairway', 'Tee Box']:
                        avg_distance = club_obj.get_average_distance_fairway() if club_obj else None
                    elif lie == 'Rough':
                        avg_distance = club_obj.get_average_distance_rough() if club_obj else None
                    else:
                        # Fallback: use general average if lie is something else
                        avg_distance = club_obj.get_average_distance() if club_obj else None
                    
                    # Only show as integer if we have a value
                    if avg_distance is not None:
                        avg_distance = int(round(avg_distance))
                    else:
                        avg_distance = None
                    
                    # Determine confidence based on probability and neighbor distance
                    # Factor in both probability and how close neighbors are
                    if prob > 0.5 and avg_neighbor_distance < np.percentile(neighbor_dists, 50):
                        confidence = 'High'
                    elif prob > 0.25:
                        confidence = 'Medium'
                    else:
                        confidence = 'Low'
                    
                    # Calculate agreement percentage (how many neighbors agree)
                    agreement = sum(1 for c in neighbor_clubs if c == club_name) / len(neighbor_clubs) if neighbor_clubs else 0
                    
                    recommendations.append({
                        'club_name': club_name,
                        'avg_dist': avg_distance,
                        'confidence': confidence,
                        'probability': round(prob * 100, 1),
                        'agreement': round(agreement * 100, 1)
                    })
                    seen_clubs.add(club_name)
                    
                    # Limit to top 10 recommendations
                    if len(recommendations) >= 10:
                        break
            
            context['recommendations'] = recommendations
            context['k_value'] = k
            context['total_shots_analyzed'] = len(X_train)
            
        except ValueError as e:
            context['error'] = f"Invalid input: {str(e)}"
        except Exception as e:
            context['error'] = f"Error generating recommendations: {str(e)}"
            # For debugging - remove in production
            import traceback
            print(f"KNN Error: {traceback.format_exc()}")

    return render(request, 'dashboard/recommendations.html', context)

@login_required
def recommendation_visualization_view(request):
    """
    Returns JSON data for KNN visualization showing all shots and the query point.
    Uses PCA to reduce dimensions to 2D for visualization.
    """
    try:
        # Get the same parameters as recommendation view
        distance_to_hole = int(request.GET.get('distance'))
        lie = request.GET.get('lie', 'Fairway')
        bend = request.GET.get('bend', 'Straight')
        shot_shape = request.GET.get('shot_shape', 'Straight')
        
        # Get all user's historical shots
        user_shots = Shot.objects.filter(club__user=request.user)
        
        if user_shots.count() < 3:
            return JsonResponse({'error': 'Not enough shot data for visualization'}, status=400)
        
        # Helper function to infer bend from shot_shape (same as recommendation_view)
        def infer_bend_from_shot_shape(shot_shape):
            if shot_shape in ['Draw', 'Hook']:
                return 'Dogleg Left'
            elif shot_shape in ['Fade', 'Slice']:
                return 'Dogleg Right'
            else:
                return 'Straight'
        
        # Prepare training data (same as recommendation_view)
        features_list = []
        clubs_list = []
        shot_ids = []
        
        for shot in user_shots:
            inferred_bend = infer_bend_from_shot_shape(shot.shot_shape)
            features_list.append([
                shot.distance,
                shot.lie,
                inferred_bend,
                shot.shot_shape
            ])
            clubs_list.append(shot.club.name)
            shot_ids.append(shot.id)
        
        # Encode categorical features
        features_array = np.array(features_list)
        distance_col = features_array[:, 0].astype(float).reshape(-1, 1)
        lie_col = features_array[:, 1]
        bend_col = features_array[:, 2]
        shot_shape_col = features_array[:, 3]
        
        lie_encoder = LabelEncoder()
        bend_encoder = LabelEncoder()
        shot_shape_encoder = LabelEncoder()
        
        lie_encoded = lie_encoder.fit_transform(lie_col).reshape(-1, 1)
        bend_encoded = bend_encoder.fit_transform(bend_col).reshape(-1, 1)
        shot_shape_encoded = shot_shape_encoder.fit_transform(shot_shape_col).reshape(-1, 1)
        
        X_train = np.hstack([distance_col, lie_encoded, bend_encoded, shot_shape_encoded])
        
        # Prepare query point
        try:
            lie_encoded_query = lie_encoder.transform([lie])[0]
        except ValueError:
            lie_encoded_query = lie_encoder.transform([lie_encoder.classes_[0]])[0]
        
        try:
            bend_encoded_query = bend_encoder.transform([bend])[0]
        except ValueError:
            bend_encoded_query = bend_encoder.transform([bend_encoder.classes_[0]])[0]
        
        try:
            shot_shape_encoded_query = shot_shape_encoder.transform([shot_shape])[0]
        except ValueError:
            shot_shape_encoded_query = shot_shape_encoder.transform([shot_shape_encoder.classes_[0]])[0]
        
        X_query = np.array([[distance_to_hole, lie_encoded_query, bend_encoded_query, shot_shape_encoded_query]])
        
        # Use PCA to reduce dimensions to 2D for visualization
        # Combine training and query data for PCA
        X_combined = np.vstack([X_train, X_query])
        pca = PCA(n_components=2)
        X_2d = pca.fit_transform(X_combined)
        
        # Split back into training and query
        X_train_2d = X_2d[:-1]
        X_query_2d = X_2d[-1:]
        
        # Find k nearest neighbors for visualization
        k = max(3, min(10, int(np.sqrt(len(X_train)))))
        knn = KNeighborsClassifier(n_neighbors=k, weights='distance')
        knn.fit(X_train, clubs_list)
        
        distances, indices = knn.kneighbors(X_query, n_neighbors=min(k, len(X_train)))
        
        # Get nearest neighbor indices
        nearest_neighbor_indices = indices[0].tolist()
        
        # Prepare data for visualization
        # Group shots by club for color coding
        unique_clubs = list(set(clubs_list))
        club_colors = {}
        colors = ['#004029', '#8B4513', '#6B4423', '#D2B48C', '#006647', '#D4AF37', '#006400', '#004d00', '#f5f5dc', '#f4e4bc']
        for i, club in enumerate(unique_clubs):
            club_colors[club] = colors[i % len(colors)]
        
        # Prepare scatter plot data
        shots_data = []
        for i, (x, y) in enumerate(X_train_2d):
            is_neighbor = i in nearest_neighbor_indices
            shots_data.append({
                'x': float(x),
                'y': float(y),
                'club': clubs_list[i],
                'distance': int(features_list[i][0]),
                'lie': features_list[i][1],
                'bend': features_list[i][2],
                'shot_shape': features_list[i][3],
                'is_neighbor': is_neighbor,
                'shot_id': shot_ids[i]
            })
        
        # Query point data
        query_data = {
            'x': float(X_query_2d[0][0]),
            'y': float(X_query_2d[0][1]),
            'distance': distance_to_hole,
            'lie': lie,
            'bend': bend,
            'shot_shape': shot_shape
        }
        
        # Get predicted club
        predicted_club = knn.predict(X_query)[0]
        
        return JsonResponse({
            'shots': shots_data,
            'query_point': query_data,
            'predicted_club': predicted_club,
            'club_colors': club_colors,
            'pca_explained_variance': [float(v) for v in pca.explained_variance_ratio_],
            'k': k
        })
        
    except Exception as e:
        import traceback
        return JsonResponse({
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)

@login_required
def clear_all_data_view(request):
    """
    Clears all shot data and rounds for the currently logged-in user.
    Keeps clubs since those are equipment.
    """
    if request.method == 'POST':
        # Get all rounds for the user (this will cascade delete all shots)
        rounds_count = GolfRound.objects.filter(user=request.user).count()
        shots_count = Shot.objects.filter(club__user=request.user).count()
        
        # Delete all rounds (shots will be cascade deleted)
        GolfRound.objects.filter(user=request.user).delete()
        
        messages.success(
            request,
            f"Successfully cleared all shot data! Deleted {rounds_count} round(s) and {shots_count} shot(s). "
            "Your clubs have been preserved."
        )
        return redirect('dashboard')
    
    # If GET request, show confirmation page
    rounds_count = GolfRound.objects.filter(user=request.user).count()
    shots_count = Shot.objects.filter(club__user=request.user).count()
    
    return render(request, 'dashboard/clear_data_confirm.html', {
        'rounds_count': rounds_count,
        'shots_count': shots_count
    })

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
        messages.error(request, "Dummy data file (dummy_shots.csv) not found in project root.")
        return redirect('dashboard')

    # 3. Check if user has clubs
    user_clubs = Club.objects.filter(user=request.user)
    if not user_clubs.exists():
        messages.error(request, "You need to have clubs in your bag first. Please sign up.")
        return redirect('dashboard')

    # 4. Create a new round for this test data
    new_round = GolfRound.objects.create(
        user=request.user, 
        course_name="Test Data Load"
    )

    # 5. Get the user's clubs into a dictionary for fast lookup
    # This turns [Club(name='Driver'), Club(name='7 Iron')]
    # into {'Driver': ClubObject, '7 Iron': ClubObject}
    user_clubs_dict = {club.name: club for club in user_clubs}
    
    shots_to_create = []
    skipped_count = 0

    # 6. Read the CSV file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                club_name = row.get('club_name', '').strip()
                
                # Find the user's *actual* club object that matches the name
                club = user_clubs_dict.get(club_name)
 
                # 7. Only create a shot if the user has that club and distance is valid
                if club and row.get('distance'):
                    try:
                        distance = int(row.get('distance'))
                        shot_shape = row.get('shot_shape', 'Straight').strip()
                        lie = row.get('lie', 'Fairway').strip()
                        
                        # Validate shot_shape and lie match the model choices
                        valid_shapes = ['Straight', 'Fade', 'Draw', 'Slice', 'Hook']
                        valid_lies = ['Fairway', 'Rough', 'Sand', 'Tee Box']
                        
                        if shot_shape not in valid_shapes:
                            shot_shape = 'Straight'
                        if lie not in valid_lies:
                            lie = 'Fairway'
                        
                        shots_to_create.append(
                            Shot(
                                golf_round=new_round,
                                club=club,
                                distance=distance,
                                shot_shape=shot_shape,
                                lie=lie
                            )
                        )
                    except (ValueError, TypeError):
                        # Skip row if distance isn't a valid number
                        skipped_count += 1
                else:
                    skipped_count += 1

        # 8. Use bulk_create to add all shots to the DB in one query
        if shots_to_create:
            Shot.objects.bulk_create(shots_to_create)
            messages.success(
                request, 
                f"Successfully loaded {len(shots_to_create)} shots from test data! "
                f"({skipped_count} rows skipped due to missing clubs or invalid data)"
            )
            # 9. Redirect to the new round's detail page
            return redirect('round_detail', round_id=new_round.id)
        else:
            messages.warning(
                request, 
                "No shots were loaded. Make sure your clubs match the club names in the CSV file."
            )
            # Delete the empty round
            new_round.delete()
            return redirect('dashboard')
        
    except Exception as e:
        # Handle file read errors
        messages.error(request, f"Error reading CSV file: {str(e)}")
        # Delete the round if it was created
        if new_round.id:
            new_round.delete()
        return redirect('dashboard')