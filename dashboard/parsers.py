"""
Launch Monitor Data Parsers
Handles parsing CSV and JSON exports from various launch monitor devices.
"""
import csv
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from io import StringIO


class LaunchMonitorParser:
    """Base parser class for launch monitor data."""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def _infer_shot_shape(self, launch_direction: Optional[float], 
                          carry_distance: Optional[float], 
                          total_distance: Optional[float]) -> Optional[str]:
        """
        Infers shot shape from launch monitor data.
        
        Logic:
        - Launch Direction (degrees): negative = left, positive = right, 0 = straight
        - Compare Carry Distance vs Total Distance to determine severity of curve
        - If total < carry significantly, indicates severe curve (Hook/Slice) - ball curved back
        - Launch direction magnitude determines severity: > 15° = severe, 5-15° = controlled
        
        Returns: 'Straight', 'Fade', 'Draw', 'Slice', or 'Hook'
        """
        # If no launch direction, can't infer
        if launch_direction is None:
            return None
        
        try:
            launch_dir = float(launch_direction)
        except (ValueError, TypeError):
            return None
        
        # Straight shot: launch direction within ±5 degrees
        if abs(launch_dir) <= 5.0:
            return 'Straight'
        
        # Calculate distance metrics (if both distances available)
        distance_loss_ratio = None
        if carry_distance is not None and total_distance is not None:
            try:
                carry = float(carry_distance)
                total = float(total_distance)
                if carry > 0:
                    # If total is significantly less than carry, indicates severe curve (ball curved back)
                    # This happens when a hook/slice causes the ball to lose distance
                    distance_loss_ratio = (carry - total) / carry
            except (ValueError, TypeError):
                pass
        
        # Determine if it's a severe curve (Hook/Slice) or controlled curve (Draw/Fade)
        is_severe = False
        
        # Check 1: Large launch angle (> 15 degrees) indicates severe curve
        if abs(launch_dir) > 15.0:
            is_severe = True
        # Check 2: If total distance is significantly less than carry (> 5% loss), severe curve
        elif distance_loss_ratio is not None and distance_loss_ratio > 0.05:
            is_severe = True
        # Check 3: Moderate launch angle (10-15 degrees) with some distance loss
        elif abs(launch_dir) > 10.0 and distance_loss_ratio is not None and distance_loss_ratio > 0.02:
            is_severe = True
        
        # Left side (negative launch direction)
        if launch_dir < 0:
            if is_severe:
                return 'Hook'  # Severe left curve
            else:
                return 'Draw'  # Controlled left curve
        
        # Right side (positive launch direction)
        else:  # launch_dir > 0
            if is_severe:
                return 'Slice'  # Severe right curve
            else:
                return 'Fade'  # Controlled right curve
    
    def parse(self, file_content: str, file_extension: str, device_type: Optional[str] = None) -> Dict:
        """
        Main entry point for parsing. Auto-detects format and device type.
        
        Returns normalized data structure:
        {
            'rounds': [...],
            'sourceDevice': str,
            'importedAt': ISO8601,
            'errors': [...],
            'warnings': [...]
        }
        """
        self.errors = []
        self.warnings = []
        
        # Auto-detect device type if not provided
        if not device_type:
            device_type = self._detect_device_type(file_content, file_extension)
        
        if file_extension.lower() == '.csv':
            return self._parse_csv(file_content, device_type)
        elif file_extension.lower() == '.json':
            return self._parse_json(file_content, device_type)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")
    
    def _detect_device_type(self, content: str, extension: str) -> str:
        """Auto-detect device type from file content."""
        if extension.lower() == '.json':
            try:
                data = json.loads(content)
                # Check for Arccos structure
                if isinstance(data, dict) and ('timestamp' in str(data) or 'clubId' in str(data)):
                    return 'Arccos Caddie'
                # Check for Garmin JSON structure
                if isinstance(data, list) and len(data) > 0:
                    if 'Date' in str(data[0]) or 'Course' in str(data[0]):
                        return 'Garmin R10'
            except:
                pass
        
        if extension.lower() == '.csv':
            # Read first few lines to detect
            lines = content.split('\n')[:5]
            header = lines[0] if lines else ''
            header_upper = header.upper()
            
            # Check for generic launch monitor format (Date, Time, Club Head Speed, Total Spin, etc.)
            if 'CLUB HEAD SPEED' in header_upper and 'TOTAL SPIN' in header_upper and 'TOTAL DISTANCE' in header_upper:
                return 'Generic Launch Monitor'
            elif 'CLUBHEADSPEED' in header_upper or 'SMASHFACTOR' in header_upper:
                return 'SkyTrak+'
            elif 'SPIN RATE' in header_upper or 'PEAK HEIGHT' in header_upper:
                return 'Flightscope Mevo+'
            elif 'DATE' in header_upper and 'COURSE' in header_upper:
                return 'Garmin R10'
        
        return 'Garmin R10'  # Default fallback
    
    def _parse_csv(self, content: str, device_type: str) -> Dict:
        """Parse CSV content based on device type."""
        if device_type == 'Garmin R10':
            return self._parse_garmin_r10_csv(content)
        elif device_type == 'SkyTrak+':
            return self._parse_skytrak_csv(content)
        elif device_type == 'Flightscope Mevo+':
            return self._parse_mevo_csv(content)
        elif device_type == 'Generic Launch Monitor':
            return self._parse_generic_launch_monitor_csv(content)
        else:
            raise ValueError(f"CSV parsing not supported for {device_type}")
    
    def _parse_json(self, content: str, device_type: str) -> Dict:
        """Parse JSON content based on device type."""
        if device_type == 'Garmin R10':
            return self._parse_garmin_r10_json(content)
        elif device_type == 'Arccos Caddie':
            return self._parse_arccos_json(content)
        else:
            raise ValueError(f"JSON parsing not supported for {device_type}")
    
    def _parse_garmin_r10_csv(self, content: str) -> Dict:
        """Parse Garmin R10 CSV export."""
        reader = csv.DictReader(StringIO(content))
        rounds_dict = {}
        
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (1 is header)
            try:
                # Extract round info
                date_str = row.get('Date', '').strip()
                course = row.get('Course', '').strip() or 'Unknown Course'
                hole = row.get('Hole', '').strip()
                club = row.get('Club', '').strip()
                
                if not date_str or not club:
                    self.warnings.append(f"Row {row_num}: Missing date or club, skipping")
                    continue
                
                # Parse date
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                except:
                    try:
                        date_obj = datetime.strptime(date_str, '%m/%d/%Y').date()
                    except:
                        self.errors.append(f"Row {row_num}: Invalid date format: {date_str}")
                        continue
                
                # Create round key
                round_key = f"{date_obj.isoformat()}_{course}"
                
                if round_key not in rounds_dict:
                    rounds_dict[round_key] = {
                        'date': date_obj.isoformat(),
                        'courseName': course,
                        'holes': {}
                    }
                
                # Parse hole number
                hole_num = 1
                if hole:
                    try:
                        hole_num = int(re.sub(r'\D', '', hole)) or 1
                    except:
                        hole_num = 1
                
                if hole_num not in rounds_dict[round_key]['holes']:
                    rounds_dict[round_key]['holes'][hole_num] = []
                
                # Parse distance (prefer TotalDistance, fallback to Distance)
                distance = None
                for dist_field in ['TotalDistance', 'Distance', 'CarryDistance']:
                    if dist_field in row and row[dist_field]:
                        try:
                            distance = int(float(row[dist_field]))
                            break
                        except:
                            continue
                
                if not distance:
                    self.warnings.append(f"Row {row_num}: No valid distance found")
                    continue
                
                # Extract optional fields
                shot_data = {
                    'club': club,
                    'distance': distance,
                    'sequenceNumber': len(rounds_dict[round_key]['holes'][hole_num]) + 1
                }
                
                # Optional launch monitor data
                if 'CarryDistance' in row and row['CarryDistance']:
                    try:
                        shot_data['carryDistance'] = int(float(row['CarryDistance']))
                    except:
                        pass
                
                if 'LaunchAngle' in row and row['LaunchAngle']:
                    try:
                        shot_data['launchAngle'] = float(row['LaunchAngle'])
                    except:
                        pass
                
                if 'BallSpeed' in row and row['BallSpeed']:
                    try:
                        shot_data['ballSpeed'] = float(row['BallSpeed'])
                    except:
                        pass
                
                if 'SideSpun' in row and row['SideSpun']:
                    try:
                        shot_data['spinRate'] = abs(float(row['SideSpun']))
                    except:
                        pass
                
                rounds_dict[round_key]['holes'][hole_num].append(shot_data)
                
            except Exception as e:
                self.errors.append(f"Row {row_num}: Error parsing row - {str(e)}")
                continue
        
        # Convert to normalized format
        rounds_list = []
        for round_key, round_data in rounds_dict.items():
            holes_list = [
                {
                    'holeNumber': hole_num,
                    'shots': shots
                }
                for hole_num, shots in sorted(round_data['holes'].items())
            ]
            rounds_list.append({
                'date': round_data['date'],
                'courseName': round_data['courseName'],
                'holes': holes_list
            })
        
        return {
            'rounds': rounds_list,
            'sourceDevice': 'Garmin R10',
            'importedAt': datetime.now().isoformat(),
            'errors': self.errors,
            'warnings': self.warnings
        }
    
    def _parse_garmin_r10_json(self, content: str) -> Dict:
        """Parse Garmin R10 JSON export."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {str(e)}")
        
        rounds_dict = {}
        
        # Handle both list and dict formats
        if isinstance(data, list):
            rounds_data = data
        elif isinstance(data, dict) and 'rounds' in data:
            rounds_data = data['rounds']
        else:
            rounds_data = [data]
        
        for round_idx, round_data in enumerate(rounds_data):
            try:
                date_str = round_data.get('Date') or round_data.get('date', '')
                course = round_data.get('Course') or round_data.get('course', 'Unknown Course')
                
                if not date_str:
                    self.warnings.append(f"Round {round_idx + 1}: Missing date, skipping")
                    continue
                
                try:
                    date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
                except:
                    try:
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                    except:
                        self.errors.append(f"Round {round_idx + 1}: Invalid date format")
                        continue
                
                round_key = f"{date_obj.isoformat()}_{course}"
                
                if round_key not in rounds_dict:
                    rounds_dict[round_key] = {
                        'date': date_obj.isoformat(),
                        'courseName': course,
                        'holes': {}
                    }
                
                # Parse shots (may be nested in Shots array or directly in round)
                shots_data = round_data.get('Shots') or round_data.get('shots') or []
                
                for shot_idx, shot in enumerate(shots_data):
                    club = shot.get('Club') or shot.get('club', '')
                    if not club:
                        continue
                    
                    hole_num = shot.get('Hole') or shot.get('hole', 1)
                    try:
                        hole_num = int(hole_num) if hole_num else 1
                    except:
                        hole_num = 1
                    
                    if hole_num not in rounds_dict[round_key]['holes']:
                        rounds_dict[round_key]['holes'][hole_num] = []
                    
                    distance = shot.get('TotalDistance') or shot.get('Distance') or shot.get('totalDistance') or shot.get('distance')
                    if not distance:
                        continue
                    
                    try:
                        distance = int(float(distance))
                    except:
                        continue
                    
                    shot_normalized = {
                        'club': str(club),
                        'distance': distance,
                        'sequenceNumber': len(rounds_dict[round_key]['holes'][hole_num]) + 1
                    }
                    
                    # Optional fields
                    for field in ['CarryDistance', 'LaunchAngle', 'BallSpeed', 'SideSpun']:
                        field_lower = field.lower()
                        value = shot.get(field) or shot.get(field_lower)
                        if value:
                            try:
                                if field == 'CarryDistance':
                                    shot_normalized['carryDistance'] = int(float(value))
                                elif field == 'LaunchAngle':
                                    shot_normalized['launchAngle'] = float(value)
                                elif field == 'BallSpeed':
                                    shot_normalized['ballSpeed'] = float(value)
                                elif field == 'SideSpun':
                                    shot_normalized['spinRate'] = abs(float(value))
                            except:
                                pass
                    
                    rounds_dict[round_key]['holes'][hole_num].append(shot_normalized)
                
            except Exception as e:
                self.errors.append(f"Round {round_idx + 1}: Error - {str(e)}")
                continue
        
        # Convert to normalized format
        rounds_list = []
        for round_key, round_data in rounds_dict.items():
            holes_list = [
                {
                    'holeNumber': hole_num,
                    'shots': shots
                }
                for hole_num, shots in sorted(round_data['holes'].items())
            ]
            rounds_list.append({
                'date': round_data['date'],
                'courseName': round_data['courseName'],
                'holes': holes_list
            })
        
        return {
            'rounds': rounds_list,
            'sourceDevice': 'Garmin R10',
            'importedAt': datetime.now().isoformat(),
            'errors': self.errors,
            'warnings': self.warnings
        }
    
    def _parse_skytrak_csv(self, content: str) -> Dict:
        """Parse SkyTrak+ CSV export."""
        reader = csv.DictReader(StringIO(content))
        rounds_dict = {}
        current_date = None
        
        for row_num, row in enumerate(reader, start=2):
            try:
                # Parse datetime
                datetime_str = row.get('DateTime', '').strip()
                if datetime_str:
                    try:
                        dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
                    except:
                        try:
                            dt = datetime.strptime(datetime_str, '%m/%d/%Y %H:%M:%S')
                        except:
                            dt = datetime.now()
                    current_date = dt.date()
                elif not current_date:
                    current_date = datetime.now().date()
                
                club = row.get('Club', '').strip()
                if not club:
                    self.warnings.append(f"Row {row_num}: Missing club, skipping")
                    continue
                
                # Get distance (prefer TotalDistance)
                distance = None
                for dist_field in ['TotalDistance', 'CarryDistance']:
                    if dist_field in row and row[dist_field]:
                        try:
                            distance = int(float(row[dist_field]))
                            break
                        except:
                            continue
                
                if not distance:
                    self.warnings.append(f"Row {row_num}: No valid distance found")
                    continue
                
                round_key = f"{current_date.isoformat()}_SkyTrak Session"
                
                if round_key not in rounds_dict:
                    rounds_dict[round_key] = {
                        'date': current_date.isoformat(),
                        'courseName': 'SkyTrak Practice Session',
                        'holes': {1: []}  # SkyTrak typically doesn't have holes
                    }
                
                shot_data = {
                    'club': club,
                    'distance': distance,
                    'sequenceNumber': len(rounds_dict[round_key]['holes'][1]) + 1
                }
                
                # Optional fields
                if 'CarryDistance' in row and row['CarryDistance']:
                    try:
                        shot_data['carryDistance'] = int(float(row['CarryDistance']))
                    except:
                        pass
                
                if 'LaunchAngle' in row and row['LaunchAngle']:
                    try:
                        shot_data['launchAngle'] = float(row['LaunchAngle'])
                    except:
                        pass
                
                if 'BallSpeed' in row and row['BallSpeed']:
                    try:
                        shot_data['ballSpeed'] = float(row['BallSpeed'])
                    except:
                        pass
                
                if 'TotalSpin' in row and row['TotalSpin']:
                    try:
                        shot_data['spinRate'] = abs(float(row['TotalSpin']))
                    except:
                        pass
                
                if 'SmashFactor' in row and row['SmashFactor']:
                    try:
                        shot_data['smashFactor'] = float(row['SmashFactor'])
                    except:
                        pass
                
                rounds_dict[round_key]['holes'][1].append(shot_data)
                
            except Exception as e:
                self.errors.append(f"Row {row_num}: Error - {str(e)}")
                continue
        
        # Convert to normalized format
        rounds_list = []
        for round_key, round_data in rounds_dict.items():
            rounds_list.append({
                'date': round_data['date'],
                'courseName': round_data['courseName'],
                'holes': [
                    {
                        'holeNumber': 1,
                        'shots': round_data['holes'][1]
                    }
                ]
            })
        
        return {
            'rounds': rounds_list,
            'sourceDevice': 'SkyTrak+',
            'importedAt': datetime.now().isoformat(),
            'errors': self.errors,
            'warnings': self.warnings
        }
    
    def _parse_mevo_csv(self, content: str) -> Dict:
        """Parse Flightscope Mevo+ CSV export."""
        reader = csv.DictReader(StringIO(content))
        rounds_dict = {}
        current_date = None
        
        for row_num, row in enumerate(reader, start=2):
            try:
                # Parse date/time
                date_str = row.get('Date', '').strip()
                time_str = row.get('Time', '').strip()
                
                if date_str:
                    try:
                        if time_str:
                            dt = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M:%S')
                        else:
                            dt = datetime.strptime(date_str, '%Y-%m-%d')
                        current_date = dt.date()
                    except:
                        try:
                            dt = datetime.strptime(date_str, '%m/%d/%Y')
                            current_date = dt.date()
                        except:
                            current_date = datetime.now().date()
                elif not current_date:
                    current_date = datetime.now().date()
                
                club = row.get('Club', '').strip()
                if not club:
                    self.warnings.append(f"Row {row_num}: Missing club, skipping")
                    continue
                
                # Get distance (prefer Total, fallback to Carry)
                distance = None
                for dist_field in ['Total', 'Carry']:
                    if dist_field in row and row[dist_field]:
                        try:
                            distance = int(float(row[dist_field]))
                            break
                        except:
                            continue
                
                if not distance:
                    self.warnings.append(f"Row {row_num}: No valid distance found")
                    continue
                
                round_key = f"{current_date.isoformat()}_Mevo Session"
                
                if round_key not in rounds_dict:
                    rounds_dict[round_key] = {
                        'date': current_date.isoformat(),
                        'courseName': 'Mevo+ Practice Session',
                        'holes': {1: []}
                    }
                
                shot_data = {
                    'club': club,
                    'distance': distance,
                    'sequenceNumber': len(rounds_dict[round_key]['holes'][1]) + 1
                }
                
                # Optional fields
                if 'Carry' in row and row['Carry']:
                    try:
                        shot_data['carryDistance'] = int(float(row['Carry']))
                    except:
                        pass
                
                if 'Launch Angle' in row and row['Launch Angle']:
                    try:
                        shot_data['launchAngle'] = float(row['Launch Angle'])
                    except:
                        pass
                
                if 'Ball Speed' in row and row['Ball Speed']:
                    try:
                        shot_data['ballSpeed'] = float(row['Ball Speed'])
                    except:
                        pass
                
                if 'Spin Rate' in row and row['Spin Rate']:
                    try:
                        shot_data['spinRate'] = abs(float(row['Spin Rate']))
                    except:
                        pass
                
                if 'Smash Factor' in row and row['Smash Factor']:
                    try:
                        shot_data['smashFactor'] = float(row['Smash Factor'])
                    except:
                        pass
                
                rounds_dict[round_key]['holes'][1].append(shot_data)
                
            except Exception as e:
                self.errors.append(f"Row {row_num}: Error - {str(e)}")
                continue
        
        # Convert to normalized format
        rounds_list = []
        for round_key, round_data in rounds_dict.items():
            rounds_list.append({
                'date': round_data['date'],
                'courseName': round_data['courseName'],
                'holes': [
                    {
                        'holeNumber': 1,
                        'shots': round_data['holes'][1]
                    }
                ]
            })
        
        return {
            'rounds': rounds_list,
            'sourceDevice': 'Flightscope Mevo+',
            'importedAt': datetime.now().isoformat(),
            'errors': self.errors,
            'warnings': self.warnings
        }
    
    def _parse_generic_launch_monitor_csv(self, content: str) -> Dict:
        """Parse generic launch monitor CSV with Date, Time, Club Head Speed, Total Spin, etc."""
        reader = csv.DictReader(StringIO(content))
        rounds_dict = {}
        first_date = None
        round_key = "Launch Monitor Practice Session"
        
        for row_num, row in enumerate(reader, start=2):
            try:
                # Parse date and time (for timestamp, but group all into one round)
                date_str = row.get('Date', '').strip().strip('"')
                time_str = row.get('Time', '').strip().strip('"')
                
                # Store first valid date for the round date
                if date_str and not first_date:
                    try:
                        # Try ISO format first (YYYY-MM-DD)
                        if time_str:
                            dt = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M:%S')
                        else:
                            dt = datetime.strptime(date_str, '%Y-%m-%d')
                        first_date = dt.date()
                    except:
                        try:
                            # Try US format (MM/DD/YYYY)
                            if time_str:
                                dt = datetime.strptime(f"{date_str} {time_str}", '%m/%d/%Y %H:%M:%S')
                            else:
                                dt = datetime.strptime(date_str, '%m/%d/%Y')
                            first_date = dt.date()
                        except:
                            pass
                
                # Get club name
                club = row.get('Club', '').strip().strip('"')
                if not club:
                    self.warnings.append(f"Row {row_num}: Missing club, skipping")
                    continue
                
                # Get distance (prefer Total Distance, fallback to Carry Distance)
                distance = None
                for dist_field in ['Total Distance (yd)', 'Total Distance', 'TotalDistance']:
                    if dist_field in row and row[dist_field]:
                        try:
                            dist_val = row[dist_field].strip().strip('"')
                            distance = int(float(dist_val))
                            break
                        except:
                            continue
                
                # If no total distance, try carry distance
                if not distance:
                    for dist_field in ['Carry Distance (yd)', 'Carry Distance', 'CarryDistance']:
                        if dist_field in row and row[dist_field]:
                            try:
                                dist_val = row[dist_field].strip().strip('"')
                                distance = int(float(dist_val))
                                break
                            except:
                                continue
                
                if not distance:
                    self.warnings.append(f"Row {row_num}: No valid distance found, skipping")
                    continue
                
                # Group all shots into a single round
                if round_key not in rounds_dict:
                    # Use first date found, or today's date if none found
                    round_date = first_date if first_date else datetime.now().date()
                    rounds_dict[round_key] = {
                        'date': round_date.isoformat(),
                        'courseName': 'Launch Monitor Practice Session',
                        'holes': {1: []}  # All shots go to hole 1 (practice session)
                    }
                
                shot_data = {
                    'club': club,
                    'distance': distance,
                    'sequenceNumber': len(rounds_dict[round_key]['holes'][1]) + 1
                }
                
                # Extract optional launch monitor data
                # Carry Distance
                for field in ['Carry Distance (yd)', 'Carry Distance', 'CarryDistance']:
                    if field in row and row[field]:
                        try:
                            val = row[field].strip().strip('"')
                            shot_data['carryDistance'] = int(float(val))
                            break
                        except:
                            pass
                
                # Launch Angle
                for field in ['Launch Angle (deg)', 'Launch Angle', 'LaunchAngle']:
                    if field in row and row[field]:
                        try:
                            val = row[field].strip().strip('"')
                            shot_data['launchAngle'] = float(val)
                            break
                        except:
                            pass
                
                # Ball Speed
                for field in ['Ball Speed (mph)', 'Ball Speed', 'BallSpeed']:
                    if field in row and row[field]:
                        try:
                            val = row[field].strip().strip('"')
                            shot_data['ballSpeed'] = float(val)
                            break
                        except:
                            pass
                
                # Club Head Speed
                for field in ['Club Head Speed (mph)', 'Club Head Speed', 'ClubHeadSpeed']:
                    if field in row and row[field]:
                        try:
                            val = row[field].strip().strip('"')
                            shot_data['clubHeadSpeed'] = float(val)
                            break
                        except:
                            pass
                
                # Total Spin / Spin Rate
                for field in ['Total Spin (rpm)', 'Total Spin', 'TotalSpin', 'Spin Rate (rpm)', 'Spin Rate']:
                    if field in row and row[field]:
                        try:
                            val = row[field].strip().strip('"')
                            shot_data['spinRate'] = abs(float(val))
                            break
                        except:
                            pass
                
                # Smash Factor
                for field in ['Smash Factor', 'SmashFactor']:
                    if field in row and row[field]:
                        try:
                            val = row[field].strip().strip('"')
                            shot_data['smashFactor'] = float(val)
                            break
                        except:
                            pass
                
                # Launch Direction
                for field in ['Launch Direction (deg)', 'Launch Direction', 'LaunchDirection']:
                    if field in row and row[field]:
                        try:
                            val = row[field].strip().strip('"')
                            shot_data['launchDirection'] = float(val)
                            break
                        except:
                            pass
                
                # Peak Height
                for field in ['Peak Height (yd)', 'Peak Height', 'PeakHeight']:
                    if field in row and row[field]:
                        try:
                            val = row[field].strip().strip('"')
                            shot_data['peakHeight'] = float(val)
                            break
                        except:
                            pass
                
                # Accuracy
                for field in ['Accuracy (yd)', 'Accuracy']:
                    if field in row and row[field]:
                        try:
                            val = row[field].strip().strip('"')
                            shot_data['accuracy'] = float(val)
                            break
                        except:
                            pass
                
                # Store timestamp if available
                if date_str and time_str:
                    try:
                        dt = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M:%S')
                        shot_data['timestamp'] = dt.isoformat()
                    except:
                        pass
                
                # Infer shot shape from launch direction and distance metrics
                shot_shape = self._infer_shot_shape(
                    launch_direction=shot_data.get('launchDirection'),
                    carry_distance=shot_data.get('carryDistance'),
                    total_distance=shot_data.get('distance')  # This is total distance
                )
                if shot_shape:
                    shot_data['shotShape'] = shot_shape
                
                rounds_dict[round_key]['holes'][1].append(shot_data)
                
            except Exception as e:
                self.errors.append(f"Row {row_num}: Error - {str(e)}")
                continue
        
        # Convert to normalized format
        rounds_list = []
        for round_key, round_data in rounds_dict.items():
            rounds_list.append({
                'date': round_data['date'],
                'courseName': round_data['courseName'],
                'holes': [
                    {
                        'holeNumber': 1,
                        'shots': round_data['holes'][1]
                    }
                ]
            })
        
        return {
            'rounds': rounds_list,
            'sourceDevice': 'Generic Launch Monitor',
            'importedAt': datetime.now().isoformat(),
            'errors': self.errors,
            'warnings': self.warnings
        }
    
    def _parse_arccos_json(self, content: str) -> Dict:
        """Parse Arccos Caddie JSON export."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {str(e)}")
        
        # Handle different JSON structures
        if isinstance(data, list):
            shots_data = data
        elif isinstance(data, dict):
            if 'shots' in data:
                shots_data = data['shots']
            elif 'rounds' in data:
                shots_data = []
                for round_data in data['rounds']:
                    if 'shots' in round_data:
                        shots_data.extend(round_data['shots'])
            else:
                shots_data = [data]
        else:
            raise ValueError("Unexpected JSON structure")
        
        rounds_dict = {}
        
        for shot_idx, shot in enumerate(shots_data):
            try:
                # Parse timestamp
                timestamp = shot.get('timestamp') or shot.get('Timestamp')
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(str(timestamp).replace('Z', '+00:00'))
                    except:
                        try:
                            dt = datetime.fromtimestamp(int(timestamp) / 1000)  # Assume milliseconds
                        except:
                            dt = datetime.now()
                else:
                    dt = datetime.now()
                
                date_obj = dt.date()
                
                # Get course name
                course = shot.get('course') or shot.get('Course') or 'Unknown Course'
                if isinstance(course, dict):
                    course = course.get('name') or 'Unknown Course'
                
                round_key = f"{date_obj.isoformat()}_{course}"
                
                if round_key not in rounds_dict:
                    rounds_dict[round_key] = {
                        'date': date_obj.isoformat(),
                        'courseName': str(course),
                        'holes': {}
                    }
                
                # Get hole number
                hole_num = shot.get('hole') or shot.get('Hole') or shot.get('holeNumber') or 1
                try:
                    hole_num = int(hole_num) if hole_num else 1
                except:
                    hole_num = 1
                
                if hole_num not in rounds_dict[round_key]['holes']:
                    rounds_dict[round_key]['holes'][hole_num] = []
                
                # Get club (may be ID, need to map or use as-is)
                club = shot.get('clubId') or shot.get('club') or shot.get('Club') or ''
                if isinstance(club, dict):
                    club = club.get('name') or club.get('id') or ''
                
                if not club:
                    self.warnings.append(f"Shot {shot_idx + 1}: Missing club, skipping")
                    continue
                
                # Get distance
                distance = shot.get('distance') or shot.get('Distance')
                if not distance:
                    self.warnings.append(f"Shot {shot_idx + 1}: Missing distance, skipping")
                    continue
                
                try:
                    distance = int(float(distance))
                except:
                    self.warnings.append(f"Shot {shot_idx + 1}: Invalid distance")
                    continue
                
                shot_data = {
                    'club': str(club),
                    'distance': distance,
                    'sequenceNumber': len(rounds_dict[round_key]['holes'][hole_num]) + 1
                }
                
                # Optional fields
                if 'accuracy' in shot:
                    try:
                        shot_data['accuracy'] = float(shot['accuracy'])
                    except:
                        pass
                
                if 'dispersion' in shot:
                    try:
                        shot_data['metadata'] = {'dispersion': float(shot['dispersion'])}
                    except:
                        pass
                
                rounds_dict[round_key]['holes'][hole_num].append(shot_data)
                
            except Exception as e:
                self.errors.append(f"Shot {shot_idx + 1}: Error - {str(e)}")
                continue
        
        # Convert to normalized format
        rounds_list = []
        for round_key, round_data in rounds_dict.items():
            holes_list = [
                {
                    'holeNumber': hole_num,
                    'shots': shots
                }
                for hole_num, shots in sorted(round_data['holes'].items())
            ]
            rounds_list.append({
                'date': round_data['date'],
                'courseName': round_data['courseName'],
                'holes': holes_list
            })
        
        return {
            'rounds': rounds_list,
            'sourceDevice': 'Arccos Caddie',
            'importedAt': datetime.now().isoformat(),
            'errors': self.errors,
            'warnings': self.warnings
        }

