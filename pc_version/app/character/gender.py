from app.models.anime import GenderEnum

class GenderResolver:
    """Resolves character gender using source hierarchy."""
    
    def resolve_gender(self, user_gender: GenderEnum, anilist_gender: GenderEnum, mal_gender: GenderEnum) -> GenderEnum:
        # Hierarchy: User Override > AniList > MAL
        
        if user_gender != GenderEnum.UNKNOWN:
            return user_gender
            
        # Detect conflict
        if (anilist_gender == GenderEnum.MALE and mal_gender == GenderEnum.FEMALE) or \
           (anilist_gender == GenderEnum.FEMALE and mal_gender == GenderEnum.MALE):
            return GenderEnum.CONFLICT
            
        if anilist_gender != GenderEnum.UNKNOWN:
            return anilist_gender
            
        if mal_gender != GenderEnum.UNKNOWN:
            return mal_gender
            
        return GenderEnum.UNKNOWN
