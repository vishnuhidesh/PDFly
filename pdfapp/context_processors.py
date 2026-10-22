from .constants import TOOLS, CATEGORIES

def tools_processor(request):
    return {
        'ALL_TOOLS': TOOLS,
        'CATEGORIES': CATEGORIES,
    }
