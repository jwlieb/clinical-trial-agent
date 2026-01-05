"""Unit tests for match_patient.py - patient-trial matching logic."""

import pytest

from src.match_patient import (
    parse_age,
    fast_filter,
    calculate_relevance_score,
    RECRUITING_STATUSES,
    MIN_RELEVANCE_SCORE,
)
from src.schemas import (
    PatientProfile,
    Trial,
    EligibilityInfo,
    FilterResult,
    MatchLikelihood,
)


class TestParseAge:
    """Tests for parse_age function."""
    
    def test_standard_format(self):
        """Standard 'N Years' format should parse."""
        assert parse_age("18 Years") == 18
        assert parse_age("65 Years") == 65
        assert parse_age("75 Years") == 75
    
    def test_various_formats(self):
        """Various age formats should parse."""
        assert parse_age("21 years") == 21
        assert parse_age("30Years") == 30
        assert parse_age("45  Years") == 45
    
    def test_months_extracts_number(self):
        """Months format extracts number (caller handles conversion)."""
        # Function extracts the number - months would be 6 here
        assert parse_age("6 Months") == 6
    
    def test_none_returns_none(self):
        """None input returns None."""
        assert parse_age(None) is None
    
    def test_empty_returns_none(self):
        """Empty string returns None."""
        assert parse_age("") is None
    
    def test_no_number_returns_none(self):
        """String with no number returns None."""
        assert parse_age("No age specified") is None


class TestCalculateRelevanceScore:
    """Tests for calculate_relevance_score function."""
    
    def test_biomarker_match_high_score(self, sample_patient, sample_trial):
        """Direct biomarker match should give high score."""
        score = calculate_relevance_score(sample_patient, sample_trial)
        assert score >= 0.5  # Biomarker match adds 0.5
    
    def test_cancer_type_match_adds_score(self, sample_patient, sample_trial):
        """Cancer type match should add to score."""
        # Trial has NSCLC in conditions, patient has NSCLC
        score = calculate_relevance_score(sample_patient, sample_trial)
        assert score >= 0.3  # Cancer type adds 0.3
    
    def test_no_match_low_score(self, sample_patient):
        """No matching criteria should give low score."""
        unrelated_trial = Trial(
            nct_id="NCT00000000",
            title="Study of Drug Y in Breast Cancer",
            status="Recruiting",
            conditions=["Breast Cancer", "HER2 Positive"],
            sponsor="Test",
            source_url="https://example.com",
        )
        score = calculate_relevance_score(sample_patient, unrelated_trial)
        assert score < MIN_RELEVANCE_SCORE
    
    def test_nsclc_abbreviation_match(self):
        """NSCLC abbreviation should match 'lung' in trial."""
        patient = PatientProfile(
            cancer_type="NSCLC",
            biomarkers=[],
            description="Patient with NSCLC",
        )
        trial = Trial(
            nct_id="NCT00000000",
            title="Lung Cancer Study",
            status="Recruiting",
            conditions=["Non-small cell lung cancer"],
            sponsor="Test",
            source_url="https://example.com",
        )
        score = calculate_relevance_score(patient, trial)
        assert score >= 0.3  # NSCLC -> lung match
    
    def test_partial_biomarker_match(self):
        """Partial biomarker match should add some score."""
        patient = PatientProfile(
            cancer_type="NSCLC",
            biomarkers=["KRAS G12C"],
            description="Patient with KRAS",
        )
        trial = Trial(
            nct_id="NCT00000000",
            title="KRAS Mutant Lung Cancer Study",  # Has "KRAS" but not full "G12C"
            status="Recruiting",
            conditions=["Lung Cancer"],
            sponsor="Test",
            source_url="https://example.com",
        )
        score = calculate_relevance_score(patient, trial)
        assert score >= 0.25  # Partial match adds 0.25
    
    def test_score_capped_at_one(self, sample_patient, sample_trial):
        """Score should never exceed 1.0."""
        score = calculate_relevance_score(sample_patient, sample_trial)
        assert score <= 1.0


class TestFastFilter:
    """Tests for fast_filter function."""
    
    def test_recruiting_trial_passes(self, sample_patient, sample_trial):
        """Recruiting trial should pass filter."""
        result = fast_filter(sample_patient, sample_trial)
        assert result.passed is True
        assert result.excluded_reason is None
    
    def test_non_recruiting_excluded(self, sample_patient, non_recruiting_trial):
        """Non-recruiting trial should be excluded."""
        result = fast_filter(sample_patient, non_recruiting_trial)
        assert result.passed is False
        assert "not actively recruiting" in result.excluded_reason.lower()
    
    def test_sex_mismatch_excluded(self, sample_patient, female_only_trial):
        """Sex mismatch should exclude trial."""
        # sample_patient is male, female_only_trial requires female
        result = fast_filter(sample_patient, female_only_trial)
        assert result.passed is False
        assert "female" in result.excluded_reason.lower()
    
    def test_sex_all_passes(self, sample_patient, sample_trial):
        """Trial accepting ALL sexes should pass."""
        assert sample_trial.eligibility.sex == "ALL"
        result = fast_filter(sample_patient, sample_trial)
        assert result.passed is True
    
    def test_age_below_minimum_excluded(self, sample_trial):
        """Patient below minimum age should be excluded."""
        young_patient = PatientProfile(
            age=16,
            description="Young patient",
            cancer_type="NSCLC",
            biomarkers=["KRAS G12C"],
        )
        # sample_trial has minimum_age="18 Years"
        result = fast_filter(young_patient, sample_trial)
        assert result.passed is False
        assert "below minimum age" in result.excluded_reason.lower()
    
    def test_age_above_maximum_excluded(self, sample_patient, age_restricted_trial):
        """Patient above maximum age should be excluded."""
        # sample_patient is 65, age_restricted_trial max is 50
        result = fast_filter(sample_patient, age_restricted_trial)
        assert result.passed is False
        assert "above maximum age" in result.excluded_reason.lower()
    
    def test_age_within_range_passes(self, sample_patient, sample_trial):
        """Patient within age range should pass."""
        # sample_patient is 65, sample_trial allows 18-85
        result = fast_filter(sample_patient, sample_trial)
        assert result.passed is True
    
    def test_phase_preference_respected(self, sample_patient, sample_trial):
        """Phase preference should exclude non-matching trials."""
        patient_with_pref = sample_patient.model_copy(
            update={"phase_preference": ["Phase 3"]}
        )
        # sample_trial is Phase 2
        result = fast_filter(patient_with_pref, sample_trial)
        assert result.passed is False
        assert "phase" in result.excluded_reason.lower()
    
    def test_phase_preference_match_passes(self, sample_patient, sample_trial):
        """Phase preference matching trial phase should pass."""
        patient_with_pref = sample_patient.model_copy(
            update={"phase_preference": ["Phase 2", "Phase 3"]}
        )
        result = fast_filter(patient_with_pref, sample_trial)
        assert result.passed is True
    
    def test_location_preference_respected(self, sample_patient, sample_trial):
        """Location preference should exclude non-matching trials."""
        patient_with_pref = sample_patient.model_copy(
            update={"location_preference": ["Japan", "Australia"]}
        )
        # sample_trial is in US and Canada
        result = fast_filter(patient_with_pref, sample_trial)
        assert result.passed is False
        assert "location" in result.excluded_reason.lower()
    
    def test_location_preference_match_passes(self, sample_patient, sample_trial):
        """Location preference matching trial location should pass."""
        patient_with_pref = sample_patient.model_copy(
            update={"location_preference": ["United States", "Germany"]}
        )
        # sample_trial is in US and Canada
        result = fast_filter(patient_with_pref, sample_trial)
        assert result.passed is True
    
    def test_location_case_insensitive(self, sample_patient, sample_trial):
        """Location matching should be case-insensitive."""
        patient_with_pref = sample_patient.model_copy(
            update={"location_preference": ["united states"]}  # lowercase
        )
        result = fast_filter(patient_with_pref, sample_trial)
        assert result.passed is True
    
    def test_low_relevance_excluded(self, sample_patient):
        """Low relevance score should exclude trial."""
        unrelated_trial = Trial(
            nct_id="NCT00000000",
            title="Diabetes Prevention Study",
            status="Recruiting",
            conditions=["Type 2 Diabetes"],
            sponsor="Test",
            source_url="https://example.com",
            eligibility=EligibilityInfo(sex="ALL"),
        )
        result = fast_filter(sample_patient, unrelated_trial)
        assert result.passed is False
        assert "relevance" in result.excluded_reason.lower()
    
    def test_missing_eligibility_passes(self, sample_patient):
        """Trial with empty eligibility data should pass to LLM stage."""
        trial_empty_elig = Trial(
            nct_id="NCT00000000",
            title="KRAS G12C NSCLC Study",
            status="Recruiting",
            conditions=["NSCLC", "KRAS G12C"],
            sponsor="Test",
            source_url="https://example.com",
            # eligibility uses default_factory, will be empty EligibilityInfo
        )
        result = fast_filter(sample_patient, trial_empty_elig)
        assert result.passed is True
    
    def test_patient_without_age_skips_age_check(self, sample_trial):
        """Patient without age should skip age filtering."""
        patient_no_age = PatientProfile(
            description="Patient without age specified",
            cancer_type="NSCLC",
            biomarkers=["KRAS G12C"],
        )
        result = fast_filter(patient_no_age, sample_trial)
        assert result.passed is True


class TestRecruitingStatuses:
    """Tests for RECRUITING_STATUSES constant."""
    
    def test_contains_recruiting(self):
        """Should contain standard recruiting statuses."""
        assert "Recruiting" in RECRUITING_STATUSES
        assert "Not yet recruiting" in RECRUITING_STATUSES
        assert "Enrolling by invitation" in RECRUITING_STATUSES
    
    def test_excludes_closed_statuses(self):
        """Should not contain closed statuses."""
        assert "Completed" not in RECRUITING_STATUSES
        assert "Terminated" not in RECRUITING_STATUSES
        assert "Withdrawn" not in RECRUITING_STATUSES
        assert "Suspended" not in RECRUITING_STATUSES

