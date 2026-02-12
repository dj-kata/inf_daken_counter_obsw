"""
日本語UI定義
すべてのUI文字列をクラスのメンバ変数として定義
VSCodeの補完が効く形式
"""


class UIText:
    """UI文字列定義クラス"""
    
    class menu:
        """メニューバー"""
        file = 'ファイル(&F)'
        tool = 'ツール(&E)'
        language = 'Language(&L)'
        help = 'ヘルプ(&H)'
        
        # ファイルメニュー
        base_config = '基本設定(&C)...'
        obs_config = 'OBS制御設定(&O)...'
        save_image = '画像保存(&S)'
        exit = '終了(&X)'
        
        # ツールメニュー
        tweet = '成果をツイート(&T)...'
        score_viewer = 'スコアビューワ起動(&S)'
        write_bpi_csv = 'BPI Manager用csvを書き出す(開発中)(&B)...'
        
        # 言語メニュー
        japanese = '日本語'
        english = 'English'
        
        # ヘルプメニュー
        about = 'バージョン情報(&A)'
        documentation = 'ドキュメント(&D)'
    
    class window:
        """ウィンドウタイトル"""
        main_title = 'INFINITAS打鍵カウンタ'
        settings_title = '基本設定'
        obs_title = 'OBS制御設定'
        about_title = 'バージョン情報'
    
    class dialog:
        """ダイアログ"""
        ok = 'OK'
        cancel = 'キャンセル'
        apply = '適用'
        close = '閉じる'
        yes = 'はい'
        no = 'いいえ'
        browse = '参照...'
        select_image_path = '画像保存先フォルダを選択'
    
    class tab:
        """設定ダイアログのタブ"""
        feature = '機能設定'
        music_pack = '楽曲パック'
        image_save = '画像保存'
        data_import = 'データ登録'
        rival = 'ライバル'
    
    class feature:
        """機能設定タブ"""
        tweet_group = 'ツイート機能'
        enable_autotweet = '終了時の自動ツイートを有効にする'
        enable_judge = '判定部分を含める'
        enable_folder_updates = 'フォルダごとの更新数を表示(開発中)'
        
        other_group = 'その他'
        image_save_path = '画像保存先:'
        autoload_offset = '自動読み込みオフセット:'
        websocket_port = 'データ表示用port:'
    
    class music_pack:
        """楽曲パック設定タブ"""
        description = '集計対象とする楽曲パックを選択してください'
        select_all = '全選択'
        deselect_all = '全解除'
    
    class image_save:
        """画像保存設定タブ"""
        condition_group = '画像保存条件'
        always = '常に保存'
        only_updates = '更新時のみ保存'
        never = '保存しない'
        
        rivalarea_group = 'ライバル欄の編集'
        rivalarea_invalid = '編集しない'
        rivalarea_mosaic = 'モザイク'
        rivalarea_cut = 'カット'
        # rivalarea_hide = '非表示にする'
        # rivalarea_custom = 'カスタム画像で置換'
        
        other_group = 'その他'
        write_statistics = '統計情報を書き込む'
    
    class data_import:
        """データ登録タブ"""
        from_images_group = '保存済みのリザルト画像から登録'
        from_images_button = 'フォルダから画像を読み込んで登録'
        from_images_description = '保存済みのリザルト画像からプレーログを登録します'
        from_images_dialog_description = 'リザルト画像のフォルダを選択'
        
        from_pkl_group = 'v2のalllog.pklから登録'
        from_pkl_button = 'alllog.pklを選択して登録'
        from_pkl_description = 'v2で出力したalllog.pklからプレーログを登録します'
        from_pkl_dialog_description = 'alllog.pklを選択してください'
        
        cancel_button = 'キャンセル'
        processing = '処理中...'
        completed_format = '完了: {total}件中{registered}件を登録しました'
        error_format = 'エラー: {message}'
    
    class rival:
        """ライバル設定タブ"""
        rival_group = 'ライバル登録'
        rival_description = 'ライバルのinf_score.csvのGoogle Drive共有URLを登録してください'
        name_label = '名前'
        url_label = 'URL'
        add_button = '追加'
        remove_button = '削除'
        csv_export_group = 'CSV出力先'
        csv_export_description = 'inf_score.csvの出力先フォルダ (空欄の場合はアプリのルート)'
        select_csv_export_path = 'CSV出力先フォルダを選択'

    class message:
        """メッセージ"""
        language_changed = '言語を変更しました。アプリケーションを再起動します...'
        config_saved = '設定を保存しました'
        restart_required = '設定を反映するには、アプリケーションを再起動してください'
        confirm_restart = '言語設定を変更します。アプリケーションを再起動しますか？'
        select_action = 'アクションを選択してください'
        select_timing = '実行タイミングを選択してください'
        select_scene_and_source = '対象シーンと対象ソースを選択してください'
        select_next_scene = '切り替え先シーンを選択してください'
        failed_add_setting = '設定の追加に失敗しました:\n{e}'
        select_setting_to_remove = '削除する設定を選択してください'
        ask_remove_all_settings = 'すべての制御設定を削除しますか?\n(監視対象ソースは削除されません)'
        removed_all_settings = "すべての制御設定を削除しました\n(監視対象ソースは保持されています)"
        reconnected_to_obs = 'OBSに再接続しました'
        failed_reconnection_to_obs = 'OBSへの再接続に失敗しました'
        failed_reconnection_to_obs_with_error = 'OBSへの再接続に失敗しました:\n{e}'
        target_source_removed = '監視対象ソースをクリアしました'

        error_title = 'エラー'
        warning_title = '警告'
        info_title = '情報'
        confirm_title = '確認'
        completed_title = '完了'
        success = '成功'

    class status:
        """ステータスバー"""
        ready = '準備完了'
        processing = '処理中...'
        saved = '保存しました'
        loading = '読み込み中...'
        canceling = 'キャンセル中...'
    
    class button:
        """ボタン"""
        ok = 'OK'
        cancel = 'キャンセル'
        clear = 'クリア'
        start = '開始'
        stop = '停止'
        pause = '一時停止'
        resume = '再開'
        reset = 'リセット'
        save = '保存'
        load = '読み込み'
        refresh = '更新'
        reconnect = '再接続'
        add_setting = '設定を追加'
        delete_selected_setting = '選択した設定を削除'
        delete_all_settings = 'すべて削除'

    class obs:
        '''OBS関連のメッセージ'''
        connection_state = 'OBS接続状態'
        status_connected = '接続中'
        status_connection_failed = '接続失敗'
        status_disconnected = '切断しました'
        status_lost = '切断されました'
        status_reconnect_failed = '再接続失敗'
        status_reconnecting = '再接続中...'
        status_reconnected = '再接続成功'
        not_configured = "設定が完了していません"
        not_connected  = "未接続"
        no_source = "監視対象ソース未設定"
        connected = '接続中'

        # 制御設定ダイアログ関連
        websocket_group = 'OBS WebSocket接続設定'
        websocket_host = 'ホスト:'
        websocket_port = 'ポート:'
        websocket_password = 'パスワード:'
        target_source_group = '監視対象ソース'
        target_source_not_set = '未設定'
        target_source_label = '現在の監視対象:'
        new_settings_group = '新しい制御設定を追加'
        new_settings_action = 'アクション:'
        new_settings_timing = '実行タイミング:'
        new_settings_target_scene = '対象シーン:'
        new_settings_source = '対象ソース:'
        new_settings_next_scene = '切り替え先シーン:'
        registered_group = '登録済み制御設定'
        timing = '実行タイミング'
        action = 'アクション'
        scene = '対象シーン'
        source = '対象ソース'
        setting_complete = '設定完了'
        source_configured = "監視対象ソースを '{target_source}' に設定しました"


    class obs_timing:
        '''OBS制御設定におけるタイミング'''
        app_start = "アプリ起動時"
        app_end = "アプリ終了時"
        select_start = "選曲画面開始時"
        select_end = "選曲画面終了時"
        play_start = "プレー画面開始時"
        play_end = "プレー画面終了時"
        result_start = "リザルト画面開始時"
        result_end = "リザルト画面終了時"

    class obs_action:
        '''OBS制御設定におけるアクション'''
        show_source = "ソースを表示"
        hide_source = "ソースを非表示"
        switch_scene = "シーンを切り替え"
        set_monitor_source = "監視対象ソース指定"

    class main:
        '''main window'''
        other_info = 'その他の情報'
        current_mode = '現在のモード:'
        ontime = '起動時間:'
        today_notes = '本日の打鍵数:'
        num_saved_results = '保存したリザルト数:'
        last_saved_song = '最後に保存した曲:'
        save_image = '画像保存 (F6)'
        status_ready = '準備完了'

    class mode:
        '''検出モード用'''
        init = '-'
        play = 'プレイ画面'
        result = 'リザルト画面'
        select = '選曲画面'
