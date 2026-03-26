/**
 API Service Layer
 ฟังก์ชันเรียก Backend API ทั้งหมด
 */

import axios from 'axios';

const API = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api',
  headers: { 'Content-Type': 'application/json' },
});

// Registration
export const registerUser = (data) =>
  API.post('/register', data);

export const registerFace = (username, frames, poses) =>
  API.post(`/register/face?username=${encodeURIComponent(username)}`, { frames, poses });

export const getRegisterChallenges = (username) =>
  API.get(`/register/challenges?username=${encodeURIComponent(username)}`);

export const registerBehavioral = (username, answers) =>
  API.post('/register/behavioral', {
    username: username,
    answers,
  });

// Authentication (4 Steps)
export const loginPassword = (username, password) =>
  API.post('/auth/login', { username, password });

export const verifyLiveness = (sessionToken, frame, challengeType) =>
  API.post('/auth/liveness', {
    session_token: sessionToken,
    frame,
    challenge_type: challengeType,
  });

export const verifyFace = (sessionToken, frame, pose = 'front', completedPoses = []) =>
  API.post('/auth/face', {
    session_token: sessionToken,
    frame,
    pose,
    completed_poses: completedPoses,
  });

export const getChallenges = (sessionToken) =>
  API.get(`/auth/challenges?session_token=${encodeURIComponent(sessionToken)}`);

export const verifyBehavioral = (sessionToken, answers) =>
  API.post('/auth/behavioral', {
    session_token: sessionToken,
    answers,
  });

export default API;
