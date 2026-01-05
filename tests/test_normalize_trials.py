"""Unit tests for normalize_trials.py - data extraction and normalization."""

import pytest
from datetime import date

from src.normalize_trials import (
    parse_date_safe,
    extract_phase,
    extract_status,
    extract_study_type,
    extract_enrollment,
    extract_interventions,
    extract_conditions,
    extract_locations,
    extract_sponsor,
    extract_eligibility,
    normalize_single_trial,
    _parse_bool,
)
from src.schemas import TrialPhase, TrialStatus


class TestParseBool:
    """Tests for _parse_bool helper."""
    
    def test_true_bool(self):
        """Boolean True should return True."""
        assert _parse_bool(True) is True
    
    def test_false_bool(self):
        """Boolean False should return False."""
        assert _parse_bool(False) is False
    
    def test_true_string(self):
        """String 'true' should return True."""
        assert _parse_bool("true") is True
        assert _parse_bool("True") is True
        assert _parse_bool("TRUE") is True
    
    def test_false_string(self):
        """String 'false' should return False."""
        assert _parse_bool("false") is False
        assert _parse_bool("False") is False
    
    def test_none_returns_none(self):
        """None should return None."""
        assert _parse_bool(None) is None
    
    def test_other_returns_none(self):
        """Non-bool/string should return None."""
        assert _parse_bool(1) is None
        assert _parse_bool([]) is None


class TestParseDateSafe:
    """Tests for parse_date_safe function."""
    
    def test_iso_format(self):
        """ISO date format should parse correctly."""
        result = parse_date_safe("2024-06-15")
        assert result == date(2024, 6, 15)
    
    def test_month_year(self):
        """Month Year format should parse (fuzzy)."""
        result = parse_date_safe("June 2024")
        assert result is not None
        assert result.year == 2024
        assert result.month == 6
    
    def test_empty_string(self):
        """Empty string should return None."""
        assert parse_date_safe("") is None
    
    def test_none(self):
        """None should return None."""
        assert parse_date_safe(None) is None
    
    def test_invalid_date(self):
        """Invalid date should return None."""
        assert parse_date_safe("not a date") is None


class TestExtractPhase:
    """Tests for extract_phase function."""
    
    def test_single_phase(self):
        """Single phase should return that phase."""
        assert extract_phase(["PHASE2"]) == "Phase 2"
        assert extract_phase(["PHASE1"]) == "Phase 1"
        assert extract_phase(["PHASE3"]) == "Phase 3"
    
    def test_phase_1_2_combination(self):
        """Phase 1 and Phase 2 should combine to Phase 1/Phase 2."""
        result = extract_phase(["PHASE1", "PHASE2"])
        assert result == "Phase 1/Phase 2"
    
    def test_phase_2_3_combination(self):
        """Phase 2 and Phase 3 should combine to Phase 2/Phase 3."""
        result = extract_phase(["PHASE2", "PHASE3"])
        assert result == "Phase 2/Phase 3"
    
    def test_early_phase_1(self):
        """Early Phase 1 should be recognized."""
        assert extract_phase(["EARLY_PHASE1"]) == "Early Phase 1"
    
    def test_empty_list(self):
        """Empty list should return None."""
        assert extract_phase([]) is None
    
    def test_none_input(self):
        """None should return None."""
        assert extract_phase(None) is None
    
    def test_unrecognized_phase(self):
        """Unrecognized phases should be filtered out."""
        assert extract_phase(["INVALID"]) is None


class TestExtractStatus:
    """Tests for extract_status function."""
    
    def test_recruiting_status(self):
        """RECRUITING should convert properly."""
        result = extract_status({"overallStatus": "RECRUITING"})
        assert result == "Recruiting"
    
    def test_completed_status(self):
        """COMPLETED should convert properly."""
        result = extract_status({"overallStatus": "COMPLETED"})
        assert result == "Completed"
    
    def test_none_module(self):
        """None module should return Unknown status."""
        result = extract_status(None)
        assert result == "Unknown status"
    
    def test_empty_status(self):
        """Empty status should return Unknown status."""
        result = extract_status({"overallStatus": ""})
        assert result == "Unknown status"
    
    def test_unknown_status_preserved(self):
        """Unknown API status should be preserved."""
        result = extract_status({"overallStatus": "SOME_NEW_STATUS"})
        assert result == "SOME_NEW_STATUS"


class TestExtractStudyType:
    """Tests for extract_study_type function."""
    
    def test_interventional(self):
        """INTERVENTIONAL should convert properly."""
        result = extract_study_type({"studyType": "INTERVENTIONAL"})
        assert result == "Interventional"
    
    def test_observational(self):
        """OBSERVATIONAL should convert properly."""
        result = extract_study_type({"studyType": "OBSERVATIONAL"})
        assert result == "Observational"
    
    def test_none_module(self):
        """None module should return None."""
        assert extract_study_type(None) is None
    
    def test_empty_type(self):
        """Empty study type should return None."""
        assert extract_study_type({"studyType": ""}) is None


class TestExtractEnrollment:
    """Tests for extract_enrollment function."""
    
    def test_valid_count(self):
        """Valid enrollment count should be extracted."""
        result = extract_enrollment({"enrollmentInfo": {"count": 200}})
        assert result == 200
    
    def test_zero_count(self):
        """Zero enrollment is valid."""
        result = extract_enrollment({"enrollmentInfo": {"count": 0}})
        assert result == 0
    
    def test_none_module(self):
        """None module should return None."""
        assert extract_enrollment(None) is None
    
    def test_missing_enrollment_info(self):
        """Missing enrollmentInfo should return None."""
        assert extract_enrollment({}) is None
    
    def test_string_count_ignored(self):
        """String count should be ignored (return None)."""
        result = extract_enrollment({"enrollmentInfo": {"count": "200"}})
        assert result is None


class TestExtractInterventions:
    """Tests for extract_interventions function."""
    
    def test_single_intervention(self):
        """Single intervention should be extracted."""
        result = extract_interventions({
            "interventions": [{"name": "Drug X", "type": "DRUG"}]
        })
        assert result == ["Drug X"]
    
    def test_multiple_interventions(self):
        """Multiple interventions should all be extracted."""
        result = extract_interventions({
            "interventions": [
                {"name": "Drug X", "type": "DRUG"},
                {"name": "Placebo", "type": "DRUG"},
            ]
        })
        assert result == ["Drug X", "Placebo"]
    
    def test_none_module(self):
        """None module should return empty list."""
        assert extract_interventions(None) == []
    
    def test_empty_interventions(self):
        """Empty interventions should return empty list."""
        assert extract_interventions({"interventions": []}) == []
    
    def test_missing_name_filtered(self):
        """Interventions without names should be filtered."""
        result = extract_interventions({
            "interventions": [
                {"name": "Drug X"},
                {"type": "DRUG"},  # No name
            ]
        })
        assert result == ["Drug X"]


class TestExtractConditions:
    """Tests for extract_conditions function."""
    
    def test_conditions_extracted(self):
        """Conditions should be extracted."""
        result = extract_conditions({"conditions": ["Lung Cancer", "NSCLC"]})
        assert result == ["Lung Cancer", "NSCLC"]
    
    def test_none_module(self):
        """None module should return empty list."""
        assert extract_conditions(None) == []
    
    def test_empty_conditions(self):
        """Empty conditions should return empty list."""
        assert extract_conditions({"conditions": []}) == []


class TestExtractLocations:
    """Tests for extract_locations function."""
    
    def test_unique_countries(self):
        """Countries should be unique and sorted."""
        result = extract_locations({
            "locations": [
                {"country": "United States", "city": "Boston"},
                {"country": "United States", "city": "New York"},
                {"country": "Germany", "city": "Berlin"},
            ]
        })
        assert result == ["Germany", "United States"]
    
    def test_none_module(self):
        """None module should return empty list."""
        assert extract_locations(None) == []
    
    def test_missing_country_filtered(self):
        """Locations without country should be filtered."""
        result = extract_locations({
            "locations": [
                {"country": "USA"},
                {"city": "Paris"},  # No country
            ]
        })
        assert result == ["USA"]


class TestExtractSponsor:
    """Tests for extract_sponsor function."""
    
    def test_sponsor_and_collaborators(self):
        """Should extract lead sponsor and collaborators."""
        sponsor, collaborators = extract_sponsor({
            "leadSponsor": {"name": "Big Pharma"},
            "collaborators": [
                {"name": "Research Institute"},
                {"name": "University"},
            ],
        })
        assert sponsor == "Big Pharma"
        assert collaborators == ["Research Institute", "University"]
    
    def test_none_module(self):
        """None module should return defaults."""
        sponsor, collaborators = extract_sponsor(None)
        assert sponsor == "Unknown"
        assert collaborators == []
    
    def test_missing_sponsor(self):
        """Missing lead sponsor should default."""
        sponsor, _ = extract_sponsor({})
        assert sponsor == "Unknown"


class TestExtractEligibility:
    """Tests for extract_eligibility function."""
    
    def test_full_eligibility(self):
        """Full eligibility info should be extracted."""
        result = extract_eligibility({
            "eligibilityCriteria": "Must be 18+",
            "minimumAge": "18 Years",
            "maximumAge": "75 Years",
            "sex": "ALL",
            "healthyVolunteers": "false",
        })
        assert result.raw_text == "Must be 18+"
        assert result.minimum_age == "18 Years"
        assert result.maximum_age == "75 Years"
        assert result.sex == "ALL"
        assert result.accepts_healthy_volunteers is False
    
    def test_none_module(self):
        """None module should return empty EligibilityInfo."""
        result = extract_eligibility(None)
        assert result.raw_text is None
        assert result.minimum_age is None


class TestNormalizeSingleTrial:
    """Tests for normalize_single_trial function."""
    
    def test_full_trial_normalization(self, raw_trial_api_response):
        """Full API response should normalize correctly."""
        trial = normalize_single_trial(raw_trial_api_response)
        
        assert trial.nct_id == "NCT99999999"
        assert trial.title == "Test Trial Official Title"
        assert trial.status == "Recruiting"
        assert trial.phase == "Phase 2"
        assert trial.study_type == "Interventional"
        assert trial.sponsor == "Pharma Corp"
        assert "Research Institute" in trial.collaborators
        assert trial.enrollment_count == 200
        assert "Drug ABC" in trial.interventions
        assert "Lung Cancer" in trial.conditions
        assert "Germany" in trial.locations
        assert "United States" in trial.locations
        assert trial.eligibility.minimum_age == "21 Years"
        assert trial.eligibility.accepts_healthy_volunteers is False
    
    def test_minimal_trial(self):
        """Minimal trial data should still normalize."""
        raw = {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT00000001"},
                "statusModule": {},
            }
        }
        trial = normalize_single_trial(raw)
        assert trial.nct_id == "NCT00000001"
        assert trial.status == "Unknown status"
    
    def test_source_url_generated(self, raw_trial_api_response):
        """Source URL should be generated from NCT ID."""
        trial = normalize_single_trial(raw_trial_api_response)
        assert "NCT99999999" in trial.source_url
        assert trial.source_url.startswith("https://clinicaltrials.gov/")

