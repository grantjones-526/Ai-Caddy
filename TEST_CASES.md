# Test Cases for Ai Caddy Club Recommendation System

This document contains test cases for the club recommendation feature. Each test case includes input parameters and expected behavior.

## Test Case Format

Each test case includes:
- **Distance**: Distance to hole in yards
- **Lie**: Current lie (Fairway, Rough, Sand, Tee Box)
- **Bend**: Hole bend (Straight, Dogleg Right, Dogleg Left)
- **Expected Result**: What should happen when these inputs are provided

---

## Short Distance Test Cases

### Test Case 1: Short Approach Shot
- **Distance**: 50 yards
- **Lie**: Fairway
- **Bend**: Straight
- **Expected Result**: Should recommend a wedge (Pitching Wedge, 52 Degree, 56 Degree, or 60 Degree) with High confidence if user has similar short-distance shots in history

### Test Case 2: Short Shot from Rough
- **Distance**: 75 yards
- **Lie**: Rough
- **Bend**: Straight
- **Expected Result**: Should recommend a wedge, potentially accounting for reduced distance from rough lie

### Test Case 3: Short Shot from Sand
- **Distance**: 30 yards
- **Lie**: Sand
- **Bend**: Straight
- **Expected Result**: Should recommend a sand wedge (56 Degree or 60 Degree) with appropriate confidence

---

## Mid-Range Distance Test Cases

### Test Case 4: Mid-Iron Approach
- **Distance**: 150 yards
- **Lie**: Fairway
- **Bend**: Straight
- **Expected Result**: Should recommend a mid-iron (6 Iron, 7 Iron, or 8 Iron) based on user's historical data

### Test Case 5: Mid-Range with Dogleg Right
- **Distance**: 175 yards
- **Lie**: Fairway
- **Bend**: Dogleg Right
- **Expected Result**: Should recommend a club that accounts for the right bend, potentially favoring clubs used with fade/slice shots historically

### Test Case 6: Mid-Range from Rough
- **Distance**: 160 yards
- **Lie**: Rough
- **Bend**: Straight
- **Expected Result**: Should recommend a club that accounts for reduced distance from rough, potentially one club stronger than fairway equivalent

---

## Long Distance Test Cases

### Test Case 7: Long Iron Shot
- **Distance**: 200 yards
- **Lie**: Fairway
- **Bend**: Straight
- **Expected Result**: Should recommend a long iron (4 Iron or 5 Iron) or hybrid/wood depending on user's bag

### Test Case 8: Fairway Wood Distance
- **Distance**: 220 yards
- **Lie**: Fairway
- **Bend**: Straight
- **Expected Result**: Should recommend a fairway wood (3 Wood or 5 Wood) or long iron

### Test Case 9: Driver Distance
- **Distance**: 280 yards
- **Lie**: Tee Box
- **Bend**: Straight
- **Expected Result**: Should recommend Driver with High confidence if user has tee box shots at similar distances

---

## Edge Cases

### Test Case 10: Very Short Distance
- **Distance**: 10 yards
- **Lie**: Fairway
- **Bend**: Straight
- **Expected Result**: Should recommend shortest wedge (60 Degree) or putter if available

### Test Case 11: Very Long Distance
- **Distance**: 350 yards
- **Lie**: Tee Box
- **Bend**: Straight
- **Expected Result**: Should recommend Driver (user's longest club) as fallback if distance exceeds historical data

### Test Case 12: Distance Beyond Historical Range
- **Distance**: 400 yards
- **Lie**: Tee Box
- **Bend**: Straight
- **Expected Result**: Should recommend user's furthest club (typically Driver) with Low confidence due to lack of similar historical data

---

## Lie-Specific Test Cases

### Test Case 13: Fairway Lie
- **Distance**: 140 yards
- **Lie**: Fairway
- **Bend**: Straight
- **Expected Result**: Should recommend club based on fairway shot history with standard distance expectations

### Test Case 14: Rough Lie
- **Distance**: 140 yards
- **Lie**: Rough
- **Bend**: Straight
- **Expected Result**: Should recommend a stronger club than fairway equivalent (e.g., 7 Iron instead of 8 Iron) due to reduced distance from rough

### Test Case 15: Sand Lie
- **Distance**: 100 yards
- **Lie**: Sand
- **Bend**: Straight
- **Expected Result**: Should recommend a sand wedge or appropriate club for sand conditions

### Test Case 16: Tee Box Lie
- **Distance**: 250 yards
- **Lie**: Tee Box
- **Bend**: Straight
- **Expected Result**: Should recommend based on tee box shot history, potentially favoring longer clubs

---

## Bend-Specific Test Cases

### Test Case 17: Dogleg Left
- **Distance**: 180 yards
- **Lie**: Fairway
- **Bend**: Dogleg Left
- **Expected Result**: Should recommend club that accounts for left bend, potentially favoring clubs used with draw/hook shots

### Test Case 18: Dogleg Right
- **Distance**: 180 yards
- **Lie**: Fairway
- **Bend**: Dogleg Right
- **Expected Result**: Should recommend club that accounts for right bend, potentially favoring clubs used with fade/slice shots

### Test Case 19: Straight Hole
- **Distance**: 180 yards
- **Lie**: Fairway
- **Bend**: Straight
- **Expected Result**: Should recommend club based on straight shot history

---

## Confidence Level Test Cases

### Test Case 20: High Confidence Scenario
- **Distance**: 150 yards
- **Lie**: Fairway
- **Bend**: Straight
- **Expected Result**: Should return High confidence if user has multiple similar shots (150±10 yards, fairway, straight) in history

### Test Case 21: Medium Confidence Scenario
- **Distance**: 165 yards
- **Lie**: Rough
- **Bend**: Dogleg Right
- **Expected Result**: Should return Medium confidence if user has some similar shots but with variations in conditions

### Test Case 22: Low Confidence Scenario
- **Distance**: 320 yards
- **Lie**: Rough
- **Bend**: Dogleg Left
- **Expected Result**: Should return Low confidence if user has few or no similar shots, with recommendation based on nearest neighbors that are far away

---

## Error Handling Test Cases

### Test Case 23: Insufficient Data
- **Distance**: 150 yards
- **Lie**: Fairway
- **Bend**: Straight
- **Expected Result**: Should display error message "Not enough shot data. You need at least 3 shots to get recommendations." if user has fewer than 3 shots in database

### Test Case 24: Invalid Distance Input
- **Distance**: "abc" (non-numeric)
- **Lie**: Fairway
- **Bend**: Straight
- **Expected Result**: Should display error message "Invalid input" and not crash

### Test Case 25: Negative Distance
- **Distance**: -50
- **Lie**: Fairway
- **Bend**: Straight
- **Expected Result**: Should handle gracefully (may show error or treat as invalid input)

### Test Case 26: Zero Distance
- **Distance**: 0
- **Lie**: Fairway
- **Bend**: Straight
- **Expected Result**: Should recommend shortest club or handle edge case appropriately

---

## Multiple Recommendation Test Cases

### Test Case 27: Close Scores
- **Distance**: 155 yards
- **Lie**: Fairway
- **Bend**: Straight
- **Expected Result**: Should return 2-3 recommendations if multiple clubs have similar confidence scores (within 15% of each other)

### Test Case 28: Clear Winner
- **Distance**: 120 yards
- **Lie**: Fairway
- **Bend**: Straight
- **Expected Result**: Should return 1-2 recommendations with clear top choice if one club significantly outperforms others

---

## Notes

- All test cases assume the user has sufficient historical shot data (minimum 3 shots)
- Expected results may vary based on individual user's historical shot patterns
- Confidence levels (High/Medium/Low) are determined by:
  - Proximity of nearest neighbors in feature space
  - Agreement among nearest neighbors
  - Number of similar historical shots
- The system uses K-Nearest Neighbors (KNN) algorithm with distance weighting
- Recommendations are personalized based on each user's unique shot history

