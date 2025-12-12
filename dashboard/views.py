from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.db.models import Avg, StdDev, Count, Q
from .models import Club, GolfRound, Shot, LaunchMonitorImport
from .parsers import LaunchMonitorParser
import os
import csv
import json
import re
import numpy as np
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.decomposition import PCA

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
def get_club_sort_order(club_name):
    """
    Returns a numeric sort order for golf clubs from Driver to Gap Wedge.
    Lower numbers appear first (Driver = 1, Gap Wedge = highest).
    """
    name_lower = club_name.lower()
    
    # Driver
    if 'driver' in name_lower:
        return 1
    
    # Woods
    if 'wood' in name_lower:
        if '3' in name_lower or 'three' in name_lower:
            return 2
        elif '5' in name_lower or 'five' in name_lower:
            return 3
        elif '7' in name_lower or 'seven' in name_lower:
            return 4
        else:
            return 5  # Other woods
    
    # Hybrids
    if 'hybrid' in name_lower:
        # Extract number if present
        numbers = re.findall(r'\d+', club_name)
        if numbers:
            num = int(numbers[0])
            return 10 + (10 - num)  # Higher number = lower sort order
        return 20
    
    # Irons
    if 'iron' in name_lower:
        numbers = re.findall(r'\d+', club_name)
        if numbers:
            num = int(numbers[0])
            # 4 Iron = 10, 5 Iron = 11, ..., 9 Iron = 15
            return 10 + (num - 4) if 4 <= num <= 9 else 20 + num
        return 30
    
    # Wedges
    if 'wedge' in name_lower or 'degree' in name_lower:
        if 'pitching' in name_lower or 'pw' in name_lower:
            return 16
        elif 'gap' in name_lower or '52' in name_lower:
            return 17
        elif 'sand' in name_lower or '56' in name_lower:
            return 18
        elif 'lob' in name_lower or '60' in name_lower:
            return 19
        else:
            # Other wedges - try to extract degree
            numbers = re.findall(r'\d+', club_name)
            if numbers:
                degree = int(numbers[0])
                if degree <= 52:
                    return 17
                elif degree <= 56:
                    return 18
                else:
                    return 19
            return 20
    
    # Default: put unknown clubs at the end
    return 100

@login_required
def dashboard_view(request):
    """Displays user's clubs and their average performance."""
    clubs = Club.objects.filter(user=request.user).annotate(
        avg_fairway=Avg('shot__distance', filter=Q(shot__lie__in=['Fairway', 'Tee Box'])),
        avg_rough=Avg('shot__distance', filter=Q(shot__lie='Rough')),
        std_dev=StdDev('shot__distance')
    ).prefetch_related('shot_set')
    
    # Sort clubs in standard golf order (Driver to Gap Wedge)
    clubs_list = list(clubs)
    clubs_list.sort(key=lambda club: (get_club_sort_order(club.name), club.name))
    
    rounds = GolfRound.objects.filter(user=request.user).order_by('-date')
    return render(request, 'dashboard/dashboard.html', {'clubs': clubs_list, 'rounds': rounds})

@login_required
def add_round_view(request):
    """Handles the creation of a new round and its associated shots."""
    if request.method == 'POST':
        course_name = request.POST.get('course_name')
        new_round = GolfRound.objects.create(user=request.user, course_name=course_name)

        # Process multiple shots submitted with the form
        clubs_ids = request.POST.getlist('club[]')
        distances = request.POST.getlist('distance[]')
        shot_shapes = request.POST.getlist('shot_shape[]')
        lies = request.POST.getlist('lie[]')

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
    context = {}
    if 'distance' in request.GET:
        try:
            distance_to_hole = int(request.GET.get('distance'))
            lie = request.GET.get('lie', 'Fairway')
            bend = request.GET.get('bend', 'Straight')
            shot_shape = request.GET.get('shot_shape', 'Straight')
            
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
                    shot.lie,           # Feature 2: Lie (categorical)
                    inferred_bend,      # Feature 3: Bend (inferred from shot_shape) (categorical)
                    shot.shot_shape     # Feature 4: Shot Shape (categorical)
                    # Add more features here in the future
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
            
            # Weights: distance=5.0, lie=10.0 (most important), bend=1.0, shot_shape=1.0
            def weighted_distance(x, y):
                """
                Custom weighted distance metric that heavily weights lie and distance.
                x, y are feature vectors: [distance, lie_encoded, bend_encoded, shot_shape_encoded]
                """
                # Extract components
                dist_diff = abs(x[0] - y[0])  # Distance difference
                lie_diff = 0 if x[1] == y[1] else 10.0  # Lie mismatch gets heavy penalty
                bend_diff = abs(x[2] - y[2])  # Bend difference
                shot_shape_diff = abs(x[3] - y[3])  # Shot shape difference
                
                # Weighted distance: lie is most important, then distance
                # Normalize distance by typical range (assume max 300 yards)
                normalized_dist = (dist_diff / 300.0) * 5.0
                normalized_bend = bend_diff * 1.0
                normalized_shot_shape = shot_shape_diff * 1.0
                
                # Combine: lie mismatch is heavily penalized, distance is important
                total_distance = lie_diff + normalized_dist + normalized_bend + normalized_shot_shape
                return total_distance
            
            # Determine optimal k (number of neighbors)
            # Use sqrt of sample size, but at least 3 and at most 10
            k = max(3, min(10, int(np.sqrt(len(X_train)))))
            
            # Train KNN classifier with custom weighted distance metric
            knn = KNeighborsClassifier(n_neighbors=k, weights='distance', metric=weighted_distance)
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
            avg_neighbor_distance = np.mean(neighbor_dists) if len(neighbor_dists) > 0 else 1
            max_possible_distance = np.max(neighbor_dists) if len(neighbor_dists) > 0 else 1
            
            # Calculate confidence factor (0-1) based on how close neighbors are
            # Closer neighbors = higher confidence
            if max_possible_distance > 0:
                distance_confidence = 1.0 / (1.0 + avg_neighbor_distance / max_possible_distance)
            else:
                distance_confidence = 1.0
            
            # Normalize club scores to probabilities
            club_probabilities = {}
            if club_scores and total_weight > 0:
                for club, score in club_scores.items():
                    # Raw probability from distance-weighted scores
                    raw_prob = score / total_weight
                    # Apply confidence factor - if neighbors are far, reduce confidence
                    # Scale between 0.6-1.0 based on distance confidence
                    adjusted_prob = raw_prob * (0.6 + 0.4 * distance_confidence)
                    # Ensure valid probability range
                    club_probabilities[club] = max(0.0, min(1.0, float(adjusted_prob)))
            
            # Get probabilities for all clubs from KNN
            all_club_probs = knn.predict_proba(X_query)[0]
            all_club_probabilities = {
                club_encoder.inverse_transform([i])[0]: float(prob) 
                for i, prob in enumerate(all_club_probs)
            }
            
            # Merge - prioritize distance-weighted scores for neighbors, use KNN prob for others
            final_probabilities = {}
            for club in all_club_probabilities:
                if club in club_probabilities:
                    # Use distance-weighted probability (from neighbors)
                    final_probabilities[club] = club_probabilities[club]
                else:
                    # Use KNN probability but scale it down since it's not in neighbors
                    final_probabilities[club] = all_club_probabilities[club] * 0.5
            
            # Get nearest neighbors details for recommendations
            recommendations = []
            seen_clubs = set()
            
            # Sort clubs by probability (highest first)
            sorted_clubs = sorted(final_probabilities.items(), key=lambda x: x[1], reverse=True)
            
            # Get club objects for easier access to model methods
            club_objects = {club.name: club for club in Club.objects.filter(user=request.user)}
            
            # Calculate a combined score: probability * agreement * distance_weight
            # This helps prioritize clubs that are both likely AND have strong neighbor agreement
            club_scores_combined = {}
            for club_name, prob in sorted_clubs:
                # Ensure probability is valid
                if np.isnan(prob) or prob < 0:
                    prob = 0.0
                
                agreement = sum(1 for c in neighbor_clubs if c == club_name) / len(neighbor_clubs) if neighbor_clubs else 0
                
                # Combined score: probability weighted by agreement and distance confidence
                # Agreement boost: clubs with more neighbor agreement get higher scores
                agreement_boost = 0.3 + 0.7 * agreement  # Scale from 0.3 to 1.0
                combined_score = prob * agreement_boost * distance_confidence
                
                # Ensure combined score is valid
                if np.isnan(combined_score) or combined_score < 0:
                    combined_score = 0.0
                
                club_scores_combined[club_name] = {
                    'probability': float(prob),
                    'agreement': float(agreement),
                    'combined_score': float(combined_score)
                }
            
            # Re-sort by combined score
            sorted_by_combined = sorted(club_scores_combined.items(), key=lambda x: x[1]['combined_score'], reverse=True)
            
            # Filter out clubs with zero or invalid scores
            valid_recommendations = [(name, data) for name, data in sorted_by_combined if data['combined_score'] > 0 and not np.isnan(data['combined_score'])]
            
            if not valid_recommendations:
                # Fallback: use just probability if combined scores are all zero
                valid_recommendations = [(name, {'probability': data['probability'], 'agreement': data['agreement'], 'combined_score': data['probability']}) 
                                        for name, data in sorted_by_combined if data['probability'] > 0]
            
            # Get club objects and calculate average distances for the specific lie
            # Re-rank recommendations by how close the club's average distance (for this lie) is to the target distance
            club_distance_rankings = []
            for club_name, score_data in valid_recommendations:
                # Never recommend Driver if lie is not Tee Box
                if club_name.lower() == 'driver' and lie != 'Tee Box':
                    continue
                
                club_obj = club_objects.get(club_name)
                if not club_obj:
                    continue
                
                # Calculate average distance based on the selected lie
                if lie in ['Fairway', 'Tee Box']:
                    avg_distance = club_obj.get_average_distance_fairway()
                elif lie == 'Rough':
                    avg_distance = club_obj.get_average_distance_rough()
                else:
                    # Fallback: use general average if lie is something else
                    avg_distance = club_obj.get_average_distance()
                
                # Only include clubs that have data for this lie
                if avg_distance is not None and avg_distance > 0:
                    # Calculate how close this club's average distance is to the target distance
                    # Lower distance_diff means better match
                    distance_diff = abs(avg_distance - distance_to_hole)
                    
                    # Combine KNN score with distance match score
                    # Clubs whose average distance is closer to target get higher priority
                    # Use inverse of distance difference (normalized) as a boost
                    # Max distance difference we care about is ~100 yards
                    distance_match_score = max(0, 1.0 - (distance_diff / 100.0))
                    
                    # Final score combines KNN combined_score with distance match
                    # Weight: 70% KNN score, 30% distance match
                    final_score = score_data['combined_score'] * 0.7 + distance_match_score * 0.3
                    
                    club_distance_rankings.append({
                        'club_name': club_name,
                        'avg_distance': avg_distance,
                        'distance_diff': distance_diff,
                        'score_data': score_data,
                        'final_score': final_score
                    })
            
            # Sort by final score (highest first), then by distance difference (closest to target first)
            club_distance_rankings.sort(key=lambda x: (x['final_score'], -x['distance_diff']), reverse=True)
            
            # Check if KNN has no good neighbors (neighbors are too far or no valid recommendations)
            # Use a threshold: if average neighbor distance is very large relative to the query distance,
            # or if we have no valid recommendations, use fallback
            use_fallback = False
            if not club_distance_rankings:
                use_fallback = True
            elif len(neighbor_dists) > 0:
                # If average neighbor distance is more than 2x the query distance, neighbors are too far
                if avg_neighbor_distance > distance_to_hole * 2:
                    use_fallback = True
            
            # Fallback: recommend furthest club in bag if KNN has no good neighbors
            if use_fallback:
                # Get all clubs for the user
                all_user_clubs = Club.objects.filter(user=request.user)
                fallback_clubs = []
                
                for club in all_user_clubs:
                    # Never recommend Driver if lie is not Tee Box
                    if club.name.lower() == 'driver' and lie != 'Tee Box':
                        continue
                    
                    # Calculate average distance based on the selected lie
                    if lie in ['Fairway', 'Tee Box']:
                        avg_distance = club.get_average_distance_fairway()
                    elif lie == 'Rough':
                        avg_distance = club.get_average_distance_rough()
                    else:
                        # Fallback: use general average if lie is something else
                        avg_distance = club.get_average_distance()
                    
                    # Only include clubs that have data for this lie
                    if avg_distance is not None and avg_distance > 0:
                        # Calculate how close this club's average distance is to the target distance
                        distance_diff = abs(avg_distance - distance_to_hole)
                        fallback_clubs.append({
                            'club_name': club.name,
                            'avg_distance': avg_distance,
                            'distance_diff': distance_diff,
                            'club_obj': club
                        })
                
                # Sort by distance difference (closest to target first)
                fallback_clubs.sort(key=lambda x: x['distance_diff'])
                
                # Add the closest matching club(s) as recommendations
                for club_data in fallback_clubs[:2]:  # Top 2 clubs closest to target distance
                    club_name = club_data['club_name']
                    avg_distance = int(round(club_data['avg_distance']))
                    
                    recommendations.append({
                        'club_name': club_name,
                        'avg_dist': avg_distance,
                        'confidence': 'Low',  # Low confidence since KNN had no good neighbors
                        'probability': 0.0,  # No probability data from KNN
                        'agreement': 0.0  # No agreement data from KNN
                    })
            else:
                # Normal KNN recommendations path
                # Get the top club's score to use as a threshold
                top_score = valid_recommendations[0][1]['combined_score'] if valid_recommendations else 0
                
                # Add top recommendations (only 1-2, or 3 if scores are very close)
                max_recommendations = 2
                min_score_threshold = top_score * 0.4  # Must be at least 40% of top score
                
                for club_data in club_distance_rankings:
                    club_name = club_data['club_name']
                    score_data = club_data['score_data']
                    avg_distance = club_data['avg_distance']
                    
                    if club_name not in seen_clubs:
                        prob = score_data['probability']
                        agreement = score_data['agreement']
                        combined_score = score_data['combined_score']
                        
                        # Skip if score is too low
                        if combined_score < min_score_threshold:
                            continue
                        
                        # Get the club object
                        club_obj = club_objects.get(club_name)
                        
                        # avg_distance is already calculated above, just format it
                        avg_distance = int(round(avg_distance))
                        
                        # Determine confidence based on combined score and neighbor distance
                        if combined_score > top_score * 0.75 and avg_neighbor_distance < np.percentile(neighbor_dists, 50) if len(neighbor_dists) > 0 else False:
                            confidence = 'High'
                        elif combined_score > top_score * 0.5:
                            confidence = 'Medium'
                        else:
                            confidence = 'Low'
                        
                        # Ensure probability is valid for display
                        display_prob = prob * 100
                        if np.isnan(display_prob) or display_prob < 0:
                            display_prob = 0.0
                        
                        recommendations.append({
                            'club_name': club_name,
                            'avg_dist': avg_distance,
                            'confidence': confidence,
                            'probability': round(display_prob, 1),
                            'agreement': round(agreement * 100, 1)
                        })
                        seen_clubs.add(club_name)
                        
                        # Limit to max recommendations (1-2, or 3 if very close scores)
                        if len(recommendations) >= max_recommendations:
                            # Check if 3rd place is very close to 2nd place (within 15%)
                            if len(valid_recommendations) > len(recommendations):
                                next_club = valid_recommendations[len(recommendations)]
                                next_score = next_club[1]['combined_score']
                                current_score = score_data['combined_score']
                                if current_score > 0 and next_score > current_score * 0.85:  # Within 15%
                                    max_recommendations = 3
                                else:
                                    break
                            else:
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
        
        # Create weighted distance metric function (same as recommendation_view)
        def weighted_distance(x, y):
            """
            Custom weighted distance metric that heavily weights lie and distance.
            x, y are feature vectors: [distance, lie_encoded, bend_encoded, shot_shape_encoded]
            """
            # Extract components
            dist_diff = abs(x[0] - y[0])  # Distance difference
            lie_diff = 0 if x[1] == y[1] else 10.0  # Lie mismatch gets heavy penalty
            bend_diff = abs(x[2] - y[2])  # Bend difference
            shot_shape_diff = abs(x[3] - y[3])  # Shot shape difference
            
            # Weighted distance: lie is most important, then distance
            # Normalize distance by typical range (assume max 300 yards)
            normalized_dist = (dist_diff / 300.0) * 5.0
            normalized_bend = bend_diff * 1.0
            normalized_shot_shape = shot_shape_diff * 1.0
            
            # Combine: lie mismatch is heavily penalized, distance is important
            total_distance = lie_diff + normalized_dist + normalized_bend + normalized_shot_shape
            return total_distance
        
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
        knn = KNeighborsClassifier(n_neighbors=k, weights='distance', metric=weighted_distance)
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

@login_required
def import_launch_monitor_view(request):
    """Handle file upload and parsing of launch monitor data."""
    if request.method == 'POST':
        if 'file' not in request.FILES:
            messages.error(request, "No file uploaded")
            return redirect('import_launch_monitor')
        
        uploaded_file = request.FILES['file']
        device_type = request.POST.get('device_type', '')
        
        # Validate file size (10MB max)
        if uploaded_file.size > 10 * 1024 * 1024:
            messages.error(request, "File size exceeds 10MB limit")
            return redirect('import_launch_monitor')
        
        # Validate file extension
        file_name = uploaded_file.name
        file_ext = os.path.splitext(file_name)[1].lower()
        if file_ext not in ['.csv', '.json']:
            messages.error(request, "Invalid file type. Please upload a CSV or JSON file")
            return redirect('import_launch_monitor')
        
        # Read file content
        try:
            if file_ext == '.json':
                file_content = uploaded_file.read().decode('utf-8')
            else:
                file_content = uploaded_file.read().decode('utf-8')
        except UnicodeDecodeError:
            messages.error(request, "File encoding error. Please ensure file is UTF-8 encoded")
            return redirect('import_launch_monitor')
        
        # Create import record
        import_record = LaunchMonitorImport.objects.create(
            user=request.user,
            device_type=device_type or 'Garmin R10',
            file_name=file_name,
            file_size=uploaded_file.size,
            raw_data=json.dumps({'content': file_content[:10000]}),  # Store first 10k chars for debugging
            status='parsing'
        )
        
        # Parse the file
        try:
            parser = LaunchMonitorParser()
            parsed_data = parser.parse(file_content, file_ext, device_type if device_type else None)
            
            # Update import record
            import_record.parsed_data = parsed_data
            import_record.status = 'preview'
            import_record.error_log = '\n'.join(parsed_data.get('errors', []))
            if parsed_data.get('warnings'):
                import_record.error_log += '\nWarnings:\n' + '\n'.join(parsed_data.get('warnings', []))
            import_record.save()
            
            # Check for duplicate rounds
            duplicate_rounds = []
            for round_data in parsed_data.get('rounds', []):
                existing = GolfRound.objects.filter(
                    user=request.user,
                    date=round_data['date'],
                    course_name=round_data['courseName']
                ).first()
                if existing:
                    duplicate_rounds.append({
                        'date': round_data['date'],
                        'course': round_data['courseName'],
                        'existing_id': existing.id
                    })
            
            return render(request, 'dashboard/import_preview.html', {
                'import_record': import_record,
                'parsed_data': parsed_data,
                'duplicate_rounds': duplicate_rounds,
                'total_rounds': len(parsed_data.get('rounds', [])),
                'total_shots': sum(
                    len(hole.get('shots', []))
                    for round_data in parsed_data.get('rounds', [])
                    for hole in round_data.get('holes', [])
                )
            })
            
        except Exception as e:
            import_record.status = 'failed'
            import_record.error_log = f"Parsing error: {str(e)}"
            import_record.save()
            messages.error(request, f"Error parsing file: {str(e)}")
            return redirect('import_launch_monitor')
    
    # GET request - show upload form
    return render(request, 'dashboard/import_launch_monitor.html', {
        'device_choices': LaunchMonitorImport.DEVICE_CHOICES
    })

def map_club_name(csv_club_name, user_clubs_dict):
    """
    Maps CSV club abbreviations to database club names.
    Handles common abbreviations like '3W' -> '3 Wood', 'LW' -> '60 Degree', etc.
    """
    csv_club = csv_club_name.strip().upper()
    
    # Direct match first
    if csv_club_name in user_clubs_dict:
        return user_clubs_dict[csv_club_name]
    
    # Case-insensitive direct match
    for club_name, club_obj in user_clubs_dict.items():
        if club_name.upper() == csv_club:
            return club_obj
    
    # Mapping dictionary for common abbreviations
    club_mappings = {
        # Woods
        'DRIVER': ['Driver'],
        '3W': ['3 Wood', '3W'],
        '5W': ['5 Wood', '5W'],
        '7W': ['7 Wood', '7W'],
        
        # Hybrids
        '2H': ['2 Hybrid', '2H', '2 Iron'],
        '3H': ['3 Hybrid', '3H', '3 Iron'],
        '4H': ['4 Hybrid', '4H', '4 Iron'],
        '5H': ['5 Hybrid', '5H', '5 Iron'],
        '6H': ['6 Hybrid', '6H', '6 Iron'],
        '7H': ['7 Hybrid', '7H', '7 Iron'],
        '8H': ['8 Hybrid', '8H', '8 Iron'],
        '9H': ['9 Hybrid', '9H', '9 Iron'],
        
        # Irons
        '2I': ['2 Iron', '2I'],
        '3I': ['3 Iron', '3I'],
        '4I': ['4 Iron', '4I'],
        '5I': ['5 Iron', '5I'],
        '6I': ['6 Iron', '6I'],
        '7I': ['7 Iron', '7I'],
        '8I': ['8 Iron', '8I'],
        '9I': ['9 Iron', '9I'],
        
        # Wedges
        'PW': ['Pitching Wedge', 'PW'],
        'GW': ['52 Degree', 'Gap Wedge', 'GW', '52°'],
        'SW': ['56 Degree', 'Sand Wedge', 'SW', '56°'],
        'LW': ['60 Degree', 'Lob Wedge', 'LW', '60°'],
        
        # Alternative wedge names
        'AW': ['52 Degree', 'Approach Wedge', 'AW', 'Gap Wedge'],
        'UW': ['52 Degree', 'Utility Wedge', 'UW'],
    }
    
    # Try mapping
    if csv_club in club_mappings:
        for possible_name in club_mappings[csv_club]:
            # Exact match
            if possible_name in user_clubs_dict:
                return user_clubs_dict[possible_name]
            # Case-insensitive match
            for club_name, club_obj in user_clubs_dict.items():
                if club_name.upper() == possible_name.upper():
                    return club_obj
            # Partial match (e.g., "52 Degree" contains "52")
            for club_name, club_obj in user_clubs_dict.items():
                if possible_name.upper() in club_name.upper() or club_name.upper() in possible_name.upper():
                    return club_obj
    
    # Try partial matching for numbers (e.g., "3W" might match "3 Wood")
    if len(csv_club) >= 2:
        number = csv_club[0] if csv_club[0].isdigit() else None
        letter = csv_club[-1] if csv_club[-1].isalpha() else None
        
        if number and letter:
            # Try to match "3W" with "3 Wood", "3H" with "3 Hybrid" or "3 Iron"
            for club_name, club_obj in user_clubs_dict.items():
                club_upper = club_name.upper()
                if club_upper.startswith(number):
                    if letter == 'W' and ('WOOD' in club_upper or 'W' in club_upper):
                        return club_obj
                    elif letter == 'H' and ('HYBRID' in club_upper or 'IRON' in club_upper):
                        return club_obj
                    elif letter == 'I' and 'IRON' in club_upper:
                        return club_obj
    
    # Try fuzzy matching - check if CSV name is contained in any club name or vice versa
    for club_name, club_obj in user_clubs_dict.items():
        club_upper = club_name.upper()
        # Remove common words for matching
        club_clean = club_upper.replace(' DEGREE', '').replace('°', '').replace(' WOOD', '').replace(' IRON', '').replace(' HYBRID', '').replace(' WEDGE', '')
        csv_clean = csv_club.replace('W', '').replace('H', '').replace('I', '').replace('P', '').replace('G', '').replace('S', '').replace('L', '')
        
        if csv_clean and csv_clean in club_clean:
            return club_obj
        if club_clean and club_clean in csv_club:
            return club_obj
    
    return None

@login_required
def confirm_import_view(request, import_id):
    """Confirm and import the parsed launch monitor data."""
    import_record = get_object_or_404(LaunchMonitorImport, id=import_id, user=request.user)
    
    if import_record.status != 'preview':
        messages.error(request, "This import is not ready for confirmation")
        return redirect('dashboard')
    
    if request.method == 'POST':
        merge_duplicates = request.POST.get('merge_duplicates') == 'on'
        parsed_data = import_record.parsed_data
        
        if not parsed_data:
            messages.error(request, "No parsed data found")
            return redirect('dashboard')
        
        rounds_created = 0
        shots_created = 0
        errors = []
        
        # Get user's clubs for matching
        user_clubs = {club.name: club for club in Club.objects.filter(user=request.user)}
        
        try:
            for round_data in parsed_data.get('rounds', []):
                # Check for duplicate
                existing_round = GolfRound.objects.filter(
                    user=request.user,
                    date=round_data['date'],
                    course_name=round_data['courseName']
                ).first()
                
                if existing_round and not merge_duplicates:
                    errors.append(f"Skipped duplicate round: {round_data['courseName']} on {round_data['date']}")
                    continue
                
                # Use existing round or create new
                if existing_round and merge_duplicates:
                    golf_round = existing_round
                else:
                    golf_round = GolfRound.objects.create(
                        user=request.user,
                        date=round_data['date'],
                        course_name=round_data['courseName']
                    )
                    rounds_created += 1
                
                # Import shots
                for hole_data in round_data.get('holes', []):
                    for shot_data in hole_data.get('shots', []):
                        club_name = shot_data.get('club', '').strip()
                        
                        # Use the mapping function to find matching club
                        club = map_club_name(club_name, user_clubs)
                        
                        if not club:
                            errors.append(f"Club '{club_name}' not found in your bag. Shot skipped.")
                            continue
                        
                        # Determine lie and shot_shape
                        # Use the mapped club name for lie determination
                        mapped_club_name = club.name
                        lie = 'Tee Box' if 'Tee' in mapped_club_name or 'Driver' in mapped_club_name else 'Fairway'
                        
                        # Use inferred shot shape from parser if available, otherwise default to Straight
                        shot_shape = shot_data.get('shotShape', 'Straight')
                        
                        # Validate shot_shape is one of the allowed choices
                        valid_shapes = ['Straight', 'Fade', 'Draw', 'Slice', 'Hook']
                        if shot_shape not in valid_shapes:
                            shot_shape = 'Straight'
                        
                        # Create shot
                        try:
                            Shot.objects.create(
                                golf_round=golf_round,
                                club=club,
                                distance=shot_data.get('distance', 0),
                                shot_shape=shot_shape,
                                lie=lie
                            )
                            shots_created += 1
                        except Exception as e:
                            errors.append(f"Error creating shot: {str(e)}")
            
            # Update import record
            import_record.status = 'imported' if not errors else 'partial'
            import_record.rounds_created = rounds_created
            import_record.shots_created = shots_created
            import_record.imported_at = timezone.now()
            if errors:
                import_record.error_log += '\n\nImport Errors:\n' + '\n'.join(errors)
            import_record.save()
            
            # Success message
            if errors:
                messages.warning(
                    request,
                    f"Import completed with {len(errors)} errors. "
                    f"Created {rounds_created} rounds and {shots_created} shots."
                )
            else:
                messages.success(
                    request,
                    f"Successfully imported {rounds_created} rounds and {shots_created} shots!"
                )
            
            return redirect('dashboard')
            
        except Exception as e:
            import_record.status = 'failed'
            import_record.error_log += f'\n\nImport error: {str(e)}'
            import_record.save()
            messages.error(request, f"Error during import: {str(e)}")
            return redirect('dashboard')
    
    # GET request - show confirmation page
    parsed_data = import_record.parsed_data
    duplicate_rounds = []
    for round_data in parsed_data.get('rounds', []) if parsed_data else []:
        existing = GolfRound.objects.filter(
            user=request.user,
            date=round_data['date'],
            course_name=round_data['courseName']
        ).first()
        if existing:
            duplicate_rounds.append({
                'date': round_data['date'],
                'course': round_data['courseName'],
                'existing_id': existing.id
            })
    
    total_shots = sum(
        len(hole.get('shots', []))
        for round_data in parsed_data.get('rounds', []) if parsed_data
        for hole in round_data.get('holes', [])
    )
    
    return render(request, 'dashboard/import_confirm.html', {
        'import_record': import_record,
        'parsed_data': parsed_data,
        'duplicate_rounds': duplicate_rounds,
        'total_rounds': len(parsed_data.get('rounds', [])) if parsed_data else 0,
        'total_shots': total_shots
    })