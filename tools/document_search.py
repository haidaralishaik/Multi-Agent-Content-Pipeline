"""
Document Search Tool - Search user's personal documents

Used by the Researcher agent to find relevant information
from the user's own notes, files, and documents.
"""

from pathlib import Path
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class DocumentSearchTool:
    """
    Searches through local documents for relevant information

    In production, this would use a vector database (FAISS, Pinecone, etc.)
    For now, it does simple keyword matching against files in data/.
    """

    def __init__(self, docs_dir: str = 'data'):
        """
        Initialize document search

        Args:
            docs_dir: Directory containing documents to search
        """
        self.docs_dir = Path(docs_dir)
        self.docs_dir.mkdir(exist_ok=True)
        self.documents = self._load_documents()
        logger.info(f"DocumentSearch initialized with {len(self.documents)} documents")

    def _load_documents(self) -> List[Dict]:
        """Load all documents from the data directory"""
        documents = []

        for filepath in self.docs_dir.glob('**/*'):
            if filepath.is_file() and filepath.suffix in ['.txt', '.md', '.pdf']:
                try:
                    content = filepath.read_text(encoding='utf-8')
                    documents.append({
                        'filename': filepath.name,
                        'path': str(filepath),
                        'content': content,
                        'size': len(content)
                    })
                except Exception as e:
                    logger.warning(f"Could not read {filepath}: {e}")

        return documents

    def search(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Search documents for relevant content

        Args:
            query: Search query
            max_results: Maximum number of results to return

        Returns:
            List of matching document excerpts with metadata
        """
        if not self.documents:
            return [{
                'source': 'No documents',
                'content': 'No documents found in data/ directory. Add .txt or .md files to enable document search.',
                'relevance': 'N/A'
            }]

        results = []
        query_terms = query.lower().split()

        for doc in self.documents:
            content_lower = doc['content'].lower()

            # Simple relevance scoring: count matching terms
            score = sum(1 for term in query_terms if term in content_lower)

            if score > 0:
                # Extract relevant excerpt (first matching section)
                excerpt = self._extract_excerpt(doc['content'], query_terms)
                results.append({
                    'source': doc['filename'],
                    'path': doc['path'],
                    'content': excerpt,
                    'relevance_score': score,
                    'relevance': 'High' if score >= 3 else 'Medium' if score >= 2 else 'Low'
                })

        # Sort by relevance score
        results.sort(key=lambda x: x['relevance_score'], reverse=True)

        return results[:max_results]

    def _extract_excerpt(self, content: str, query_terms: List[str], context_chars: int = 500) -> str:
        """Extract relevant excerpt around matching terms"""
        content_lower = content.lower()

        for term in query_terms:
            pos = content_lower.find(term)
            if pos != -1:
                start = max(0, pos - context_chars // 2)
                end = min(len(content), pos + context_chars // 2)
                excerpt = content[start:end]
                if start > 0:
                    excerpt = "..." + excerpt
                if end < len(content):
                    excerpt = excerpt + "..."
                return excerpt

        # If no match found, return beginning of document
        return content[:context_chars] + ("..." if len(content) > context_chars else "")


# Example usage
if __name__ == "__main__":
    search = DocumentSearchTool()
    results = search.search("RAG retrieval augmented generation")
    print(f"Found {len(results)} results:")
    for r in results:
        print(f"  - {r['source']}: {r['relevance']}")
