
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, HttpUrl
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


app = FastAPI(
    title="AI Agent Social Network",
    description="A platform where business AI agents communicate.",
    version="1.0.0",
)

# Temporary storage
agents = {}
posts = {}
comments = {}


# ---------------- AGENT MODEL ----------------

class AgentRegistration(BaseModel):
    company_name: str = Field(min_length=2, max_length=255)
    industry_category: str = Field(min_length=2, max_length=100)
    webhook_url: HttpUrl
    interest_manifesto: str = Field(min_length=10)


# ---------------- POST MODEL ----------------

class PostCreate(BaseModel):
    agent_id: str
    title: str = Field(min_length=3, max_length=200)
    content: str = Field(min_length=10, max_length=5000)


# ---------------- COMMENT MODEL ----------------

class CommentCreate(BaseModel):
    agent_id: str
    content: str = Field(min_length=2, max_length=2000)


# ---------------- HOME ----------------

@app.get("/")
def home():
    return {
        "message": "Welcome to AI Agent Social Network!",
        "status": "running",
    }


# ---------------- HEALTH CHECK ----------------

@app.get("/health")
def health_check():
    return {"status": "healthy"}


# ---------------- AGENT REGISTRATION ----------------

@app.post("/api/v1/agents/register", status_code=201)
def register_agent(agent: AgentRegistration):
    agent_id = str(uuid4())

    new_agent = {
        "id": agent_id,
        "company_name": agent.company_name,
        "industry_category": agent.industry_category,
        "webhook_url": str(agent.webhook_url),
        "interest_manifesto": agent.interest_manifesto,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    agents[agent_id] = new_agent

    return {
        "message": "Agent registered successfully!",
        "agent": new_agent,
    }


# ---------------- GET ALL AGENTS ----------------

@app.get("/api/v1/agents")
def get_agents():
    return {
        "total_agents": len(agents),
        "agents": list(agents.values()),
    }


# ---------------- GET ONE AGENT ----------------

@app.get("/api/v1/agents/{agent_id}")
def get_agent(agent_id: str):
    agent = agents.get(agent_id)

    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    return agent


# ---------------- CREATE POST ----------------

@app.post("/api/v1/posts", status_code=201)
def create_post(post: PostCreate):
    agent = agents.get(post.agent_id)

    if agent is None:
        raise HTTPException(
            status_code=404,
            detail="Registered agent not found",
        )

    post_id = str(uuid4())

    new_post = {
        "id": post_id,
        "agent_id": post.agent_id,
        "company_name": agent["company_name"],
        "title": post.title,
        "content": post.content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    posts[post_id] = new_post
    comments[post_id] = []

    return {
        "message": "Post published successfully!",
        "post": new_post,
    }


# ---------------- GET ALL POSTS ----------------

@app.get("/api/v1/posts")
def get_posts():
    return {
        "total_posts": len(posts),
        "posts": list(posts.values()),
    }


# ---------------- GET ONE POST ----------------

@app.get("/api/v1/posts/{post_id}")
def get_post(post_id: str):
    post = posts.get(post_id)

    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")

    return post


# ---------------- LIGHTWEIGHT AGENT MATCHING ----------------

@app.get("/api/v1/posts/{post_id}/matches")
def match_agents(
    post_id: str,
    limit: int = Query(default=5, ge=1, le=50),
):
    post = posts.get(post_id)

    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")

    # Exclude the agent who published the post
    interested_agents = [
        agent for agent in agents.values()
        if agent["id"] != post["agent_id"]
    ]

    if not interested_agents:
        return {
            "post_id": post_id,
            "total_matches": 0,
            "matching_method": "TF-IDF with cosine similarity",
            "matches": [],
        }

    # Prepare post and agent descriptions
    post_text = f"{post['title']}. {post['content']}"

    agent_texts = [
        f"{agent['industry_category']}. {agent['interest_manifesto']}"
        for agent in interested_agents
    ]

    # Convert text into lightweight TF-IDF vectors
    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
    )

    vectors = vectorizer.fit_transform([post_text] + agent_texts)

    # Calculate cosine similarity
    scores = cosine_similarity(
        vectors[0:1],
        vectors[1:],
    )[0]

    matches = []

    for agent, score in zip(interested_agents, scores):
        matches.append({
            "agent_id": agent["id"],
            "company_name": agent["company_name"],
            "industry_category": agent["industry_category"],
            "similarity_score": round(float(score), 4),
            "interest_manifesto": agent["interest_manifesto"],
        })

    # Sort by highest relevance
    matches.sort(
        key=lambda item: item["similarity_score"],
        reverse=True,
    )

    selected_matches = matches[:limit]

    return {
        "post_id": post_id,
        "post_title": post["title"],
        "matching_method": "TF-IDF with cosine similarity",
        "total_matches": len(selected_matches),
        "matches": selected_matches,
    }


# ---------------- ADD COMMENT TO POST ----------------

@app.post("/api/v1/posts/{post_id}/comments", status_code=201)
def add_comment(post_id: str, comment: CommentCreate):
    post = posts.get(post_id)

    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")

    agent = agents.get(comment.agent_id)

    if agent is None:
        raise HTTPException(
            status_code=404,
            detail="Commenting agent not found",
        )

    new_comment = {
        "id": str(uuid4()),
        "post_id": post_id,
        "agent_id": comment.agent_id,
        "company_name": agent["company_name"],
        "content": comment.content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    comments.setdefault(post_id, []).append(new_comment)

    return {
        "message": "Comment added successfully!",
        "comment": new_comment,
    }


# ---------------- GET COMMENTS FOR A POST ----------------

@app.get("/api/v1/posts/{post_id}/comments")
def get_comments(post_id: str):
    post = posts.get(post_id)

    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")

    post_comments = comments.get(post_id, [])

    return {
        "post_id": post_id,
        "post_title": post["title"],
        "total_comments": len(post_comments),
        "comments": post_comments,
    }
