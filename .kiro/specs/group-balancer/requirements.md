# Requirements Document

## Introduction

The Group Balancer system is a Python application that automatically distributes people into balanced groups based on their scores and advantage status. The system reads participant data from an Excel file and creates groups that minimize score variance while ensuring fair distribution of advantaged participants.

## Glossary

- **Group_Balancer**: The main Python application system that performs group distribution
- **Participant**: An individual person with a name, score, and optional advantage status
- **Advantage_Status**: A special designation indicated by an asterisk (*) suffix in a participant's name
- **Group_Average**: The arithmetic mean of all participant scores within a single group
- **Score_Variance**: The statistical measure of how spread out group averages are from each other
- **Excel_Data_Source**: The XLSX file containing participant names and scores
- **Group_Count**: The number of groups to create, specified as a command-line argument

## Requirements

### Requirement 1

**User Story:** As a group organizer, I want to specify the number of groups via command-line arguments, so that I can control how many groups are created for my event.

#### Acceptance Criteria

1. WHEN the user runs the program with a group count argument THEN the Group_Balancer SHALL accept the number and use it for group creation
2. WHEN the user provides an invalid group count (non-positive integer) THEN the Group_Balancer SHALL reject the input and display an error message
3. WHEN the user runs the program without arguments THEN the Group_Balancer SHALL display usage instructions
4. WHEN the group count exceeds the number of participants THEN the Group_Balancer SHALL handle this gracefully and inform the user

### Requirement 2

**User Story:** As a group organizer, I want the system to read participant data from an Excel file, so that I can maintain participant information in a familiar format.

#### Acceptance Criteria

1. WHEN the Group_Balancer processes an Excel file THEN the system SHALL extract participant names and scores from the specified columns
2. WHEN a participant name contains an asterisk (*) suffix THEN the Group_Balancer SHALL identify them as having Advantage_Status
3. WHEN the Excel file is missing or corrupted THEN the Group_Balancer SHALL report the error and terminate gracefully
4. WHEN the Excel file contains invalid score data THEN the Group_Balancer SHALL validate numeric scores and report any issues
5. WHEN parsing participant data THEN the Group_Balancer SHALL preserve the original name format while extracting Advantage_Status

### Requirement 3

**User Story:** As a group organizer, I want advantaged participants distributed evenly across groups, so that no single group has an unfair concentration of advantages.

#### Acceptance Criteria

1. WHEN distributing participants with Advantage_Status THEN the Group_Balancer SHALL spread them as evenly as possible across all groups
2. WHEN the number of advantaged participants is not evenly divisible by group count THEN the Group_Balancer SHALL minimize the maximum difference in advantaged participants per group
3. WHEN assigning advantaged participants THEN the Group_Balancer SHALL ensure no group receives more than one additional advantaged participant compared to others
4. WHEN there are multiple advantaged participants to distribute THEN the Group_Balancer SHALL consider their individual scores to balance the average impact across groups

### Requirement 4

**User Story:** As a group organizer, I want group averages to be as close as possible, so that competition or collaboration is fair across all groups.

#### Acceptance Criteria

1. WHEN creating groups THEN the Group_Balancer SHALL minimize the Score_Variance between Group_Average values
2. WHEN calculating group balance THEN the Group_Balancer SHALL consider both participant scores and Advantage_Status distribution
3. WHEN multiple grouping solutions exist THEN the Group_Balancer SHALL select the solution with the lowest Score_Variance
4. WHEN displaying results THEN the Group_Balancer SHALL show each Group_Average to help verify balance

### Requirement 5

**User Story:** As a group organizer, I want to see the final group assignments with statistics, so that I can verify the grouping meets my requirements.

#### Acceptance Criteria

1. WHEN grouping is complete THEN the Group_Balancer SHALL display each group with its members and Group_Average
2. WHEN showing results THEN the Group_Balancer SHALL indicate which participants have Advantage_Status
3. WHEN presenting group statistics THEN the Group_Balancer SHALL show the overall Score_Variance across groups
4. WHEN displaying output THEN the Group_Balancer SHALL format results in a clear, readable manner
5. WHEN generating Excel output THEN the Group_Balancer SHALL create a file with each group showing member names and individual scores
6. WHEN creating Excel output THEN the Group_Balancer SHALL include a summary sheet with highest score, lowest score, average, median, and standard deviation
7. WHEN producing Excel results THEN the Group_Balancer SHALL save the file with a descriptive name including timestamp