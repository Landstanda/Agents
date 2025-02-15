#!/usr/bin/env python3

import re
import unicodedata
from typing import List, Dict, Union, Any, Optional
import pandas as pd
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)

class DataCleanerModule:
    """Module for cleaning and standardizing data."""
    
    def __init__(self):
        self.date_formats = [
            "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", 
            "%Y/%m/%d", "%d-%m-%Y", "%m-%d-%Y",
            "%Y.%m.%d", "%d.%m.%Y", "%m.%d.%Y"
        ]
    
    def normalize_text(self, text: str, lowercase: bool = True) -> str:
        """
        Normalize text by removing extra whitespace, normalizing unicode, etc.
        
        Args:
            text (str): Text to normalize
            lowercase (bool): Whether to convert to lowercase
            
        Returns:
            str: Normalized text
        """
        try:
            if not isinstance(text, str):
                return str(text)
                
            # Normalize unicode characters and remove accents
            text = unicodedata.normalize('NFKD', text)
            text = ''.join(c for c in text if not unicodedata.combining(c))
            
            # Remove extra whitespace
            text = re.sub(r'\s+', ' ', text).strip()
            
            if lowercase:
                text = text.lower()
                
            return text
        except Exception as e:
            logger.error(f"Failed to normalize text: {str(e)}")
            return text
            
    def standardize_date(self, date_str: str) -> Optional[str]:
        """
        Convert various date formats to ISO format (YYYY-MM-DD).
        Assumes DD/MM/YYYY format for ambiguous dates.
        
        Args:
            date_str (str): Date string to standardize
            
        Returns:
            str: Standardized date in ISO format, or None if invalid
        """
        try:
            # First try ISO format (YYYY-MM-DD)
            try:
                return datetime.strptime(date_str, "%Y-%m-%d").strftime('%Y-%m-%d')
            except ValueError:
                pass
                
            # Then try DD/MM/YYYY formats
            for separator in ['/', '-', '.']:
                try:
                    return datetime.strptime(date_str, f"%d{separator}%m{separator}%Y").strftime('%Y-%m-%d')
                except ValueError:
                    continue
                    
            return None
        except Exception as e:
            logger.error(f"Failed to standardize date: {str(e)}")
            return None
            
    def remove_duplicates(self, data: List[Any]) -> List[Any]:
        """
        Remove duplicate items from a list while preserving order.
        
        Args:
            data (List): List of items to deduplicate
            
        Returns:
            List: Deduplicated list
        """
        try:
            seen = set()
            return [x for x in data if not (x in seen or seen.add(x))]
        except Exception as e:
            logger.error(f"Failed to remove duplicates: {str(e)}")
            return data
            
    def clean_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean dictionary values by normalizing strings and standardizing dates.
        
        Args:
            data (Dict): Dictionary to clean
            
        Returns:
            Dict: Cleaned dictionary
        """
        try:
            cleaned = {}
            for key, value in data.items():
                if isinstance(value, str):
                    # Try to parse as date first
                    date_value = self.standardize_date(value)
                    if date_value:
                        cleaned[key] = date_value
                    else:
                        cleaned[key] = self.normalize_text(value)
                elif isinstance(value, (list, tuple)):
                    cleaned[key] = self.remove_duplicates(value)
                elif isinstance(value, dict):
                    cleaned[key] = self.clean_dict(value)
                else:
                    cleaned[key] = value
            return cleaned
        except Exception as e:
            logger.error(f"Failed to clean dictionary: {str(e)}")
            return data
            
    def standardize_phone(self, phone: str) -> Optional[str]:
        """
        Standardize phone numbers to E.164 format.
        
        Args:
            phone (str): Phone number to standardize
            
        Returns:
            str: Standardized phone number, or None if invalid
        """
        try:
            # Remove all non-digit characters
            digits = re.sub(r'\D', '', phone)
            
            # Handle different formats
            if len(digits) == 10:  # US number without country code
                return f"+1{digits}"
            elif len(digits) == 11 and digits.startswith('1'):  # US number with country code
                return f"+{digits}"
            elif len(digits) >= 11:  # International number
                return f"+{digits}"
            return None
        except Exception as e:
            logger.error(f"Failed to standardize phone number: {str(e)}")
            return None
            
    def clean_email(self, email: str) -> Optional[str]:
        """
        Clean and validate email addresses.
        
        Args:
            email (str): Email address to clean
            
        Returns:
            str: Cleaned email address, or None if invalid
        """
        try:
            # Basic email validation regex
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            
            # Normalize and clean
            email = self.normalize_text(email, lowercase=True)
            
            if re.match(email_pattern, email):
                return email
            return None
        except Exception as e:
            logger.error(f"Failed to clean email: {str(e)}")
            return None
            
    def clean_dataframe(self, df: pd.DataFrame, date_columns: List[str] = None) -> pd.DataFrame:
        """
        Clean an entire pandas DataFrame.
        
        Args:
            df (pd.DataFrame): DataFrame to clean
            date_columns (List[str]): List of column names containing dates
            
        Returns:
            pd.DataFrame: Cleaned DataFrame
        """
        try:
            # Create a copy to avoid modifying the original
            cleaned_df = df.copy()
            
            # Handle date columns
            if date_columns:
                for col in date_columns:
                    if col in cleaned_df.columns:
                        cleaned_df[col] = cleaned_df[col].apply(
                            lambda x: self.standardize_date(str(x)) if pd.notnull(x) else None
                        )
            
            # Clean string columns
            for col in cleaned_df.select_dtypes(include=['object']).columns:
                cleaned_df[col] = cleaned_df[col].apply(
                    lambda x: self.normalize_text(str(x)) if pd.notnull(x) else None
                )
            
            return cleaned_df
        except Exception as e:
            logger.error(f"Failed to clean DataFrame: {str(e)}")
            return df
            
    def clean_json(self, json_str: str) -> Optional[str]:
        """
        Clean and validate JSON data.
        
        Args:
            json_str (str): JSON string to clean
            
        Returns:
            str: Cleaned JSON string, or None if invalid
        """
        try:
            # Parse JSON to validate and clean nested data
            data = json.loads(json_str)
            
            # Clean the parsed data
            if isinstance(data, dict):
                cleaned_data = self.clean_dict(data)
            elif isinstance(data, list):
                cleaned_data = [
                    self.clean_dict(item) if isinstance(item, dict) else item 
                    for item in data
                ]
            else:
                cleaned_data = data
                
            # Convert back to JSON string
            return json.dumps(cleaned_data, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to clean JSON: {str(e)}")
            return None 