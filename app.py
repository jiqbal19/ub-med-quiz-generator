with col2:
    st.subheader("3. Generated Quiz Output")
    
    if st.session_state.is_generating:
        st.components.v1.html("""
            <script>
            window.addEventListener('beforeunload', function (e) {
                e.preventDefault();
                e.returnValue = '';
            });
            </script>
        """, height=0)

        status_box = st.empty()
        progress_bar = st.progress(0)
        output_container = st.empty()
        
        status_box.info("⚡ Preparing lecture slides for AI context...")
        progress_bar.progress(15)
        
        combined_styles = ""
        session_instructions = ""
        inline_slide_context = ""
        
        k = len(selected_session_titles)
        base_quota = num_questions // k
        remainder = num_questions % k
        
        try:
            for idx, title in enumerate(selected_session_titles):
                quota = base_quota + (1 if idx < remainder else 0)
                sess = sessions_dict[title]
                slides_text = sess.get("slides", "")

                status_box.info(f"⚡ Processing slides for session '{title}' ({idx + 1}/{k})...")

                # Strip redundant whitespace lines to compress context
                cleaned_slides = "\n".join([line.strip() for line in slides_text.splitlines() if line.strip()])
                if not cleaned_slides:
                    cleaned_slides = "No slide text content provided."

                # Append slide text directly into inline prompt context for maximum compatibility
                inline_slide_context += f"\n\n=========================================\nFULL LECTURE SLIDES FOR SESSION: '{title}'\n=========================================\n{cleaned_slides}\n"
                
                session_instructions += f"\n- Session '{title}': Generate exactly {quota} question(s)."
                
                sess_style = sess.get("style_profile")
                if sess_style:
                    combined_styles += f"\n--- Faculty Writing Style Guidelines for {title} ---\n" + sess_style
                elif global_course_style:
                    combined_styles += f"\n--- Course-Wide Faculty Writing Style Guidelines ---\n" + global_course_style

            progress_bar.progress(40)
            status_box.info("🧠 Analyzing slide contents & matching faculty writing style...")

            prompt = f"""
            You are a medical school faculty member writing completely original, high-yield in-house exam practice questions for students enrolled in {selected_course}.
            
            --- LECTURE SLIDES REFERENCE DATA ---
            {inline_slide_context}

            --- CRITICAL GROUNDING & ORIGINALITY RULES ---
            1. STRICT SCOPE & ORIGINALITY: All questions, options, and distractors MUST be grounded STRICTLY in facts explicitly stated in the provided lecture slide documents above. Read through all slides completely. Do NOT copy or closely paraphrase specific questions from existing practice sets.
            2. INDISTINGUISHABLE FACULTY STYLE: Match the faculty's exact tone, clinical vignette complexity, stem phrasing, and distractor design so closely that the AI-generated questions are indistinguishable from real faculty exam questions.
            3. OBJECTIVES ALIGNMENT: Locate the "Session/Lecture Learning Objectives" (usually on early slides) for each session document. Ensure every question directly tests a stated session learning objective.
            4. SINGLE SESSION ASSIGNMENT: Each question corresponds to EXACTLY ONE lecture session document.
            5. NO LATEX: Do NOT use LaTeX delimiters or math formatting (e.g., do NOT use $, $$, \\frac, \\text). Write all numerical values, units, and chemical formulas using plain text and standard characters only (e.g., write "mg/dL", "alpha-1", "H2O", "10-15%", "greater than", "less than").
            
            --- ANSWER KEY RANDOMIZATION & CITATION RULES ---
            6. RANDOMIZED CORRECT ANSWER DISTRIBUTION: You MUST vary the correct answer position randomly across options A, B, C, D, and E. Avoid clustering correct answers on B or C. Distribute correct keys unpredictably across the set (e.g., A, D, E, B, C) so option placement cannot be guessed by students.
            7. SPECIFIC SLIDE NUMBER CITATIONS: In Section 2, every question rationale MUST cite the exact slide/page number where the fact was derived from the document (e.g., "Exact Slide Citation: Slide 14 - Gastric Acid Phase Control").

            --- TARGET QUESTION DISTRIBUTION PER SESSION ---
            {session_instructions}

            --- IN-HOUSE FACULTY QUESTION WRITING STYLE GUIDELINES ---
            Emulate the exact tone, vignette structure, stem phrasing, and distractor style outlined below:
            {combined_styles if combined_styles else "Write clear, high-yield in-house medical school exam questions based strictly on the slides."}

            --- ARRANGEMENT & FORMATTING ---
            * Total Questions to generate: {num_questions}.
            * Arrangement Mode requested: '{arrange_mode}'.
              - If 'By Session': Group all questions for Session 1 together, then Session 2, etc.
              - If 'Shuffle': Interleave and shuffle the questions across the selected sessions randomly.
            
            Format your output clearly into two main sections:
            
            SECTION 1: QUESTIONS
            For each question, output ONLY the clean question header and stem. Do NOT include the session title in Section 1.
            Format:
            Question [Number]
            [Vignette / Stem]
            A) ...
            B) ...
            C) ...
            D) ...
            E) ...

            SECTION 2: ANSWER KEY & RATIONALES
            For each question, explicitly state the corresponding session title, correct letter, rationale, and specific slide number here.
            Format:
            Question [Number]
            - Session: [Session Title]
            - Correct Answer: [Letter A-E]
            - Detailed Rationale: Explaining why the correct option is right based on slide facts, and why each distractor is incorrect.
            - Exact Slide Citation: Slide [Number] ([Slide Topic/Heading])

            --- REQUIRED FOOTER ---
            At the very end of your response, output a blank line followed exactly by:
            Generated by Jacobs Practice Question Generator, in accordance with the JSMBS Generative Artificial Intelligence Use Policy for Medical Students in the Medical Curriculum.
            """

            full_text = ""
            STALL_TIMEOUT = 60

            def _consume_next(iterator):
                return next(iterator)

            # Cycle through model chain if a model fails or returns empty text
            for target_model in MODEL_CHAIN:
                for attempt in range(2):
                    try:
                        status_box.info(f"✍️ Generating questions using engine `{target_model}`...")
                        response = run_with_timeout(
                            client.models.generate_content_stream,
                            45,
                            model=target_model,
                            contents=[prompt]
                        )
                        
                        full_text = ""
                        chunk_count = 0
                        response_iter = iter(response)
                        
                        while True:
                            try:
                                chunk = run_with_timeout(_consume_next, STALL_TIMEOUT, response_iter)
                            except StopIteration:
                                break
                            if chunk.text:
                                full_text += chunk.text
                                chunk_count += 1
                                current_prog = min(60 + (chunk_count * 2), 98)
                                progress_bar.progress(current_prog)
                                output_container.text_area("Live Stream Output:", value=full_text, height=450)

                        if full_text.strip():
                            break  # Successfully generated text
                    except Exception as model_err:
                        err_str = str(model_err)
                        if "503" in err_str or "UNAVAILABLE" in err_str or "404" in err_str:
                            time.sleep(2)
                            continue
                        else:
                            break
                if full_text.strip():
                    break

            if not full_text.strip():
                raise Exception(
                    "The AI engines returned an empty response. Please try generating again."
                )

            st.session_state.generated_quiz = full_text
            st.session_state.is_generating = False
            st.rerun()

        except Exception as e:
            print(f"[{datetime.now().isoformat()}] Quiz generation failed: {e}")
            traceback.print_exc()

            st.session_state.is_generating = False
            status_box.empty()
            progress_bar.empty()
            st.error(f"Error generating questions: {e}")

    elif st.session_state.generated_quiz:
        st.success("🎉 Practice Quiz Active")
        
        tb_col1, tb_col2, tb_col3 = st.columns([6, 1.5, 1.5])
        
        with tb_col2:
            st.download_button(
                label="📄 .TXT",
                data=st.session_state.generated_quiz,
                file_name=f"{selected_course.replace(' ', '_')}_Practice_Quiz.txt",
                mime="text/plain",
                use_container_width=True
            )
            
        with tb_col3:
            docx_data = create_docx(st.session_state.generated_quiz)
            st.download_button(
                label="📝 .DOCX",
                data=docx_data,
                file_name=f"{selected_course.replace(' ', '_')}_Practice_Quiz.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True
            )
            
        st.code(st.session_state.generated_quiz, language="markdown")

    else:
        st.info("Select options on the left and click 'Generate Practice Quiz' to create questions.")
